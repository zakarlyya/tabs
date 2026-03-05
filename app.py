from flask import Flask, render_template, request, jsonify
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import json
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

MODEL = "gpt-5.2" # always use the latest model

STRING_CONVENTION = """STRING NAMING CONVENTION (critical — the instructor's perspective looking down at the guitar):
- "top string" = low E (6th string, thickest, closest to ceiling)
- "bottom string" = high e (1st string, thinnest, closest to floor)
- "second string from the top" = A (5th string)
- "second string from the bottom" = B (2nd string)
- "third string from the top" = D (4th string)
- "third string from the bottom" = G (3rd string)"""

PASS1_PROMPT = f"""You are a guitar lesson transcription analyzer. Your job is to read a messy, unedited transcript of a guitar lesson and produce a clean, precise summary of the instructional content.

{STRING_CONVENTION}

Do the following:
1. Identify the song title, artist, tuning, and capo position.
2. Identify each UNIQUE section of the song (e.g. Verse/Main Riff, Pre-Chorus, Chorus, Bridge). Each distinct musical part should be its own section.
3. For each section, extract ONLY the instructional content — chord shapes described as exact finger placements on specific strings and frets, strumming patterns, and special techniques (hammer-ons, pull-offs, slides, muting, etc.). Be extremely precise: quote the exact fret numbers and string positions.
4. Determine the arrangement — the order sections are played from beginning to end of the song, including repeats.

REMOVE all filler, jokes, tangents, self-commentary, and non-instructional content. Keep ONLY precise playing instructions.

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
      "raw_instructions": "Extremely detailed extraction of every chord shape with EXACT finger-on-fret-on-string positions, strumming patterns, and techniques. Use the string convention above. Include every detail."
    }}
  ]
}}"""

PASS2_PROMPT = f"""You are a precise guitar chord voicing parser. You will receive a clean description of one section of a guitar song. Extract every chord voicing into structured data.

{STRING_CONVENTION}

The "frets" array has exactly 6 values in order: [low_E, A, D, G, B, high_e]
- Number = fret to press (0 = open string)
- "x" = muted or not played

Work through each chord carefully:
- Map each described finger position to the correct string index
- low_E is index 0, A is index 1, D is index 2, G is index 3, B is index 4, high_e is index 5
- Double-check your mapping before outputting

For strumming: D = down strum, U = up strum.

Return ONLY valid JSON:
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
            return call_openai(
                client,
                PASS2_PROMPT,
                f"Section: {summary['name']}\n\n{summary['raw_instructions']}",
            )

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
