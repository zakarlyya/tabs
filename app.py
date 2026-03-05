from flask import Flask, render_template, request, jsonify
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import json
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

MODEL = "gpt-5.2" # always use the latest model

STRING_CONVENTION = """STRING NAMING CONVENTION — the instructor is looking DOWN at the guitar while playing:

By position (visual, looking down at the guitar):
- "top string" = low E = 6th string (thickest, nearest the ceiling)
- "second string from the top" or "second from the top" = A = 5th string
- "third string from the top" or "third from the top" = D = 4th string
- "fourth string from the top" or "fourth from the top" = G = 3rd string
- "fourth string from the bottom" or "fourth from the bottom" = D = 4th string
- "third string from the bottom" or "third from the bottom" = G = 3rd string
- "second string from the bottom" or "second from the bottom" = B = 2nd string
- "second to bottom" or "second to bottom string" = B = 2nd string
- "bottom string" = high e = 1st string (thinnest, nearest the floor)
- "bottom two strings" or "bottom two" = B and high e
- "top two strings" = low E and A

By number (standard guitar notation — counts from thinnest to thickest):
- "1st string" or "first string" = high e (thinnest)
- "2nd string" or "second string" = B
- "3rd string" or "third string" = G
- "4th string" or "fourth string" = D
- "5th string" or "fifth string" = A
- "6th string" or "sixth string" = low E (thickest)

By name (the instructor may use the string's note name directly):
- "the low E string" or "the E string" (context: thickest) = low E = 6th string
- "the A string" = A = 5th string
- "the D string" = D = 4th string
- "the G string" = G = 3rd string
- "the B string" = B = 2nd string
- "the high e string" or "the e string" (context: thinnest) = high e = 1st string

Other vocabulary:
- "open" = fret 0 (string played without fretting)
- "muted", "mute it", "dead", "don't play", "skip" = x
- "barre at fret N" = all covered strings set to fret N (unless a specific finger overrides a string)
- If a string is not mentioned for a STANDARD chord, infer from the standard voicing
- If a string is not mentioned for a NON-STANDARD or unusual voicing, assume open (0) unless context suggests muted"""

PASS1_PROMPT = f"""You are a guitar lesson transcription analyzer. Read a messy transcript and produce clean, precise, per-chord breakdowns.

{STRING_CONVENTION}

CRITICAL METHOD — for each chord you MUST:
1. First quote the exact words from the transcript that describe the chord.
2. Then reason step-by-step: for each phrase the instructor uses, identify WHICH physical string it refers to and WHY.
3. Then write the final per-string breakdown.

This chain-of-thought reasoning is mandatory. It prevents mistakes.

═══ WORKED EXAMPLE 1 ═══
Instructor says: "a D chord is as follows middle finger second fret on the bottom string ring finger third fret on the second string from the bottom then your pointer finger plays the second fret on the third string from the bottom ... your thumb just comes up over the back of the neck and touches the top string to mute that top string"

Reasoning:
- "bottom string" → high e (1st string, thinnest, at the floor) → middle finger, 2nd fret → high e = 2
- "second string from the bottom" → B (2nd string) → ring finger, 3rd fret → B = 3
- "third string from the bottom" → G (3rd string) → pointer finger, 2nd fret → G = 2
- D (4th string): not mentioned → standard D voicing leaves this open → D = 0
- A (5th string): not mentioned → standard D voicing skips this → A = x
- "top string" → low E (6th string, thickest, at the ceiling) → muted by thumb → low E = x

Chord: D
  low E (6th) = x  [muted by thumb — "top string" = low E]
  A (5th)     = x  [not played — standard D voicing]
  D (4th)     = 0  [open — not mentioned, standard D]
  G (3rd)     = 2  [pointer finger, 2nd fret — "third string from the bottom" = G]
  B (2nd)     = 3  [ring finger, 3rd fret — "second string from the bottom" = B]
  high e (1st)= 2  [middle finger, 2nd fret — "bottom string" = high e]

═══ WORKED EXAMPLE 2 ═══
Instructor says: "this is a c add nine chord so this is top string you want it muted by your thumb middle fingers playing the third fret on the second string from the top pointer fingers playing second fret on the third string from the top ring fingers on the third fret of the second string from the bottom ... and then pinky plays the third fret on the bottom string"

Reasoning:
- "top string" → low E (6th string) → muted by thumb → low E = x
- "second string from the top" → A (5th string) → middle finger, 3rd fret → A = 3
- "third string from the top" → D (4th string) → pointer, 2nd fret → D = 2
- G (3rd string): not mentioned → standard Cadd9 leaves this open → G = 0
- "second string from the bottom" → B (2nd string) → ring, 3rd fret → B = 3
- "bottom string" → high e (1st string) → pinky, 3rd fret → high e = 3

Chord: Cadd9
  low E (6th) = x  [muted by thumb — "top string"]
  A (5th)     = 3  [middle finger, 3rd fret — "second string from the top" = A]
  D (4th)     = 2  [pointer finger, 2nd fret — "third string from the top" = D]
  G (3rd)     = 0  [open — not mentioned, standard Cadd9]
  B (2nd)     = 3  [ring finger, 3rd fret — "second string from the bottom" = B]
  high e (1st)= 3  [pinky, 3rd fret — "bottom string" = high e]

═══ WORKED EXAMPLE 3 (barre chord) ═══
Instructor says: "Bm is a barre chord at the second fret, index finger barres across all six strings at fret two, then ring finger third fret on the fourth string, pinky goes fourth fret on the fourth string — wait no, ring finger and pinky on the fourth fret of the third and fourth strings, and ring goes on fourth fret of the fifth string too"

Reasoning:
- Barre at fret 2: index finger holds all strings at fret 2 as the base
- "fifth string" = A (5th string) → ring finger, 4th fret → A = 4
- "fourth string" = D (4th string) → pinky, 4th fret → D = 4
- "third and fourth strings" → G (3rd) and D (4th) → 4th fret → G = 4, D = 4
- low E (6th): barre gives fret 2 but Bm typically mutes this → low E = x
- B (2nd): barre gives fret 2 → B = 3 (ring covers it at fret 3) → B = 3
- high e (1st): barre gives fret 2 → high e = 2

Chord: Bm
  low E (6th) = x  [not played — standard Bm voicing]
  A (5th)     = 2  [index barre, 2nd fret]
  D (4th)     = 4  [ring or pinky, 4th fret]
  G (3rd)     = 4  [pinky, 4th fret]
  B (2nd)     = 3  [ring finger, 3rd fret]
  high e (1st)= 2  [index barre, 2nd fret]

═══ CRITICAL: RELATIVE / INCREMENTAL CHORD DESCRIPTIONS ═══

Instructors very often describe chords as MODIFICATIONS of the previous chord:
  - "add your pinky to the 3rd fret of the bottom string" → previous chord + high e = 3
  - "take off / pull off / get rid of your pointer and middle finger" → those strings become open (0)
  - "keep your ring finger in the same spot" → ring finger stays where it was
  - "get rid of your pinky" → the string the pinky was on becomes open or reverts to barre
  - "same shape but slide up to the 7th fret" → shift every fretted position up by the difference
  - "take this exact same chord and move it two frets up" → add 2 to every fretted value

You MUST resolve every relative description into a COMPLETE chord with all 6 strings.
NEVER output "same as before" — always write out the full resolved chord.

WORKED EXAMPLE 4 (relative description):
Previous chord was Bm: [x, 2, 4, 4, 3, 2]
Instructor says: "get rid of your pinky and strum — we just changed it from a B minor to a B minor seven"

Reasoning:
- Previous chord Bm has pinky on G (3rd string) = 4
- "get rid of your pinky" → G reverts to barre value = 2
- All other strings unchanged
- Result: Bm7 = [x, 2, 4, 2, 3, 2]

Chord: Bm7
  low E (6th) = x   [still not played]
  A (5th)     = 2   [still index barre]
  D (4th)     = 4   [still ring finger]
  G (3rd)     = 2   [was pinky on 4, now reverts to barre at 2]
  B (2nd)     = 3   [still middle finger]
  high e (1st)= 2   [still index barre]

═══ CRITICAL: MOVABLE SHAPES / SLIDING ═══

When the instructor describes a chord shape and then says "slide it up to fret N" or "move this same shape up two frets", apply the fret offset to all FRETTED strings. Open and muted strings stay the same.

WORKED EXAMPLE 5 (sliding shape):
Instructor says: "ring finger seventh fret on the top string, pointer fifth fret on the third string from the top, pinky seventh fret on the third string from the bottom, bottom two strings open, mute the A string"

Chord at 7th fret:
  low E (6th) = 7  [ring finger]
  A (5th)     = x  [muted]
  D (4th)     = 5  [pointer]
  G (3rd)     = 7  [pinky]
  B (2nd)     = 0  [open]
  high e (1st)= 0  [open]

Then: "take this exact same shape and move it two frets up"
→ Fretted values shift +2: 7→9, 5→7, 7→9. Open/muted stay the same.

Chord at 9th fret:
  low E (6th) = 9  [ring finger]
  A (5th)     = x  [muted]
  D (4th)     = 7  [pointer]
  G (3rd)     = 9  [pinky]
  B (2nd)     = 0  [open]
  high e (1st)= 0  [open]

YOUR TASK:
1. Identify the song title, artist, tuning, and capo.
2. Identify each UNIQUE section of the song.
3. For EVERY chord in each section: quote the transcript, reason step-by-step, then write the full 6-string breakdown. Do NOT skip strings or use shorthand.
4. Include strumming patterns and special techniques (hammer-ons, pull-offs, slides, etc.).
5. Determine the arrangement — the full order sections play start to finish.
6. REMOVE all filler, jokes, tangents. Keep ONLY playing instructions.

Return JSON:
{{
  "title": "Song Title",
  "artist": "Artist Name",
  "tuning": "Standard",
  "capo": 0,
  "arrangement": [
    {{
      "section": "Section Name",
      "label": "Display label (e.g. Intro, Verse 1, Chorus)",
      "repeat": 1,
      "notes": "Optional brief context"
    }}
  ],
  "section_summaries": [
    {{
      "name": "Section Name",
      "transcript_excerpts": "Key verbatim quotes from the transcript describing the chords in this section.",
      "raw_instructions": "For each chord: (1) the transcript quote, (2) step-by-step string reasoning, (3) the 6-string breakdown in exact format shown. Then strumming pattern and technique notes."
    }}
  ]
}}"""

PASS2_PROMPT = f"""You are a precise guitar chord voicing parser. Convert per-string chord descriptions into frets arrays.

{STRING_CONVENTION}

The output "frets" array has exactly 6 values: [low_E, A, D, G, B, high_e]
  Index 0 = low E (6th string)
  Index 1 = A (5th string)
  Index 2 = D (4th string)
  Index 3 = G (3rd string)
  Index 4 = B (2nd string)
  Index 5 = high e (1st string)

Values: integer = fret number (0 = open), "x" = muted/not played.

You will receive both:
  - "Transcript excerpts": key verbatim quotes from the original lesson (ground truth)
  - "Chord breakdown": a structured per-string analysis

When they conflict, trust the transcript excerpts.

WORKED EXAMPLE:
  Input:
    Chord: D
      low E (6th) = x  [muted by thumb]
      A (5th)     = x  [not played]
      D (4th)     = 0  [open]
      G (3rd)     = 2  [pointer, 2nd fret]
      B (2nd)     = 3  [ring, 3rd fret]
      high e (1st)= 2  [middle, 2nd fret]
  Output: {{"name": "D", "frets": ["x", "x", 0, 2, 3, 2]}}

SANITY-CHECK TABLE — for STANDARD chord names only (use as a cross-check, not as an override):
  C     → ["x", 3, 2, 0, 1, 0]
  Cadd9 → ["x", 3, 2, 0, 3, 3]
  D     → ["x", "x", 0, 2, 3, 2]
  Dm    → ["x", "x", 0, 2, 3, 1]
  E     → [0, 2, 2, 1, 0, 0]
  Em    → [0, 2, 2, 0, 0, 0]
  Em7   → [0, 2, 2, 0, 3, 0]  (or [0, 2, 0, 0, 3, 0])
  F     → [1, 1, 2, 3, 3, 1]  (full barre at 1st fret)
  G     → [3, 2, 0, 0, 3, 3]  (or [3, 2, 0, 0, 0, 3])
  A     → ["x", 0, 2, 2, 2, 0]
  Am    → ["x", 0, 2, 2, 1, 0]
  Bm    → ["x", 2, 4, 4, 3, 2]  (barre at 2nd fret)
  Bm7   → ["x", 2, 4, 2, 3, 2]  (barre, no pinky on G)
  B     → ["x", 2, 4, 4, 4, 2]  (barre at 2nd fret)
  F#    → [2, 4, 4, 3, 2, 2]    (or F#7: [2, 4, 4, 3, 2, 0])
  F#m   → [2, 4, 4, 2, 2, 2]    (barre at 2nd fret)

IMPORTANT: Many songs use non-standard voicings, partial chords, slash chords (e.g. G/B, D/F#), diminished chords, and movable shapes at higher frets.
- Do NOT "correct" a non-standard voicing to match the table above.
- The transcript description is ALWAYS the primary authority.
- The table is ONLY for catching obvious errors on common standard chord names.
- Chords with unusual names or slashes are NOT in the table — trust the per-string breakdown for those.

For strumming notation: D = down strum, U = up strum.

Return ONLY valid JSON (no extra text):
{{
  "chords": [
    {{
      "name": "Chord Name",
      "frets": ["x", "x", 0, 2, 3, 2]
    }}
  ],
  "strumming": "D U U U D U D U",
  "instructions": "Concise playing instructions and techniques for this section."
}}"""


def call_openai(client, system_prompt, user_content):
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    return json.loads(resp.choices[0].message.content)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/editor")
def editor():
    return render_template("editor.html")


@app.route("/api/generate", methods=["POST"])
def generate():
    data = request.json
    transcript = data.get("transcript", "")
    api_key = os.getenv("OPENAI_API_KEY", "")

    if not api_key:
        return jsonify({"error": "OPENAI_API_KEY not set. Add it to your .env file."}), 400
    if not transcript:
        return jsonify({"error": "Please provide a transcript."}), 400

    try:
        client = OpenAI(api_key=api_key)

        # Pass 1: analyze full transcript → clean section summaries + arrangement
        pass1 = call_openai(
            client,
            PASS1_PROMPT,
            f"Extract sections and structure from this guitar lesson transcript:\n\n{transcript}",
        )

        summaries = pass1.get("section_summaries", [])

        # Pass 2: parse each section's chords in parallel
        def parse_section(summary):
            excerpts = summary.get("transcript_excerpts", "")
            user_msg = f"Section: {summary['name']}\n\n"
            if excerpts:
                user_msg += f"Transcript excerpts:\n{excerpts}\n\n"
            user_msg += f"Chord breakdown:\n{summary['raw_instructions']}"
            return call_openai(client, PASS2_PROMPT, user_msg)

        section_details = {}
        with ThreadPoolExecutor(max_workers=min(len(summaries), 8)) as pool:
            futures = {
                pool.submit(parse_section, s): s["name"] for s in summaries
            }
            for future in as_completed(futures):
                name = futures[future]
                section_details[name] = future.result()

        # Merge pass 1 metadata with pass 2 chord details
        sections = []
        for summary in summaries:
            detail = section_details.get(summary["name"], {})
            sections.append(
                {
                    "name": summary["name"],
                    "chords": detail.get("chords", []),
                    "strumming": detail.get("strumming", ""),
                    "instructions": detail.get("instructions", ""),
                }
            )

        result = {
            "title": pass1.get("title", "Untitled"),
            "artist": pass1.get("artist", ""),
            "tuning": pass1.get("tuning", "Standard"),
            "capo": pass1.get("capo", 0),
            "sections": sections,
            "arrangement": pass1.get("arrangement", []),
        }

        return jsonify(result)

    except json.JSONDecodeError:
        return jsonify({"error": "Failed to parse LLM response as JSON."}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=3000)
