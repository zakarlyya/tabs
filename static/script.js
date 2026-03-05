document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("generate-btn");
  const transcriptInput = document.getElementById("transcript");
  const loadingEl = document.getElementById("loading");
  const errorEl = document.getElementById("error");
  const outputEl = document.getElementById("output");
  const loadFileInput = document.getElementById("load-file");

  btn.addEventListener("click", run);

  loadFileInput.addEventListener("change", () => {
    const file = loadFileInput.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const data = JSON.parse(e.target.result);
        errorEl.classList.add("hidden");
        render(data);
      } catch {
        errorEl.textContent = "Invalid file — could not parse tabs JSON.";
        errorEl.classList.remove("hidden");
      } finally {
        loadFileInput.value = "";
      }
    };
    reader.readAsText(file);
  });

  async function run() {
    const transcript = transcriptInput.value.trim();

    if (!transcript) return showError("Please enter a transcript.");

    errorEl.classList.add("hidden");
    outputEl.classList.add("hidden");
    loadingEl.classList.remove("hidden");
    btn.disabled = true;

    try {
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transcript }),
      });

      const data = await res.json();

      if (!res.ok) {
        showError(data.error || "Something went wrong.");
        return;
      }

      render(data);
    } catch {
      showError("Failed to connect to the server.");
    } finally {
      loadingEl.classList.add("hidden");
      btn.disabled = false;
    }
  }

  function showError(msg) {
    errorEl.textContent = msg;
    errorEl.classList.remove("hidden");
    loadingEl.classList.add("hidden");
    btn.disabled = false;
  }

  function esc(str) {
    const d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
  }

  function slugify(str) {
    return str.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
  }

  function render(data) {
    let html = "";

    html += `<div class="song-header">`;
    html += `<div class="song-header-top">`;
    html += `<div>`;
    html += `<h2>${esc(data.title || "Untitled")}</h2>`;
    const metaParts = [];
    if (data.artist) metaParts.push(esc(data.artist));
    if (data.tuning) metaParts.push(esc(data.tuning) + " tuning");
    if (data.capo) metaParts.push("Capo " + esc(String(data.capo)));
    if (metaParts.length) {
      html += `<div class="meta">${metaParts.join(" &middot; ")}</div>`;
    }
    html += `</div>`;
    html += `<button class="btn-ghost" id="download-btn">Download tabs</button>`;
    html += `</div>`;
    html += `</div>`;

    const arrangement = data.arrangement || [];
    if (arrangement.length) {
      html += `<div class="arrangement">`;
      html += `<div class="arrangement-title">Song Structure</div>`;
      html += `<div class="arrangement-timeline">`;
      for (let i = 0; i < arrangement.length; i++) {
        const step = arrangement[i];
        const anchor = slugify(step.section);
        const repeat = step.repeat && step.repeat > 1 ? ` &times;${step.repeat}` : "";
        const notes = step.notes ? `<span class="step-notes">${esc(step.notes)}</span>` : "";
        html += `<a href="#section-${anchor}" class="step" data-index="${i + 1}">`;
        html += `<span class="step-label">${esc(step.label || step.section)}${repeat}</span>`;
        html += notes;
        html += `</a>`;
        if (i < arrangement.length - 1) {
          html += `<span class="step-arrow">&rarr;</span>`;
        }
      }
      html += `</div></div>`;
    }

    for (const section of data.sections || []) {
      const anchor = slugify(section.name);
      html += `<div class="section" id="section-${anchor}">`;
      html += `<div class="section-name">${esc(section.name)}</div>`;

      if (section.chords && section.chords.length) {
        html += renderChordTabs(section.chords);
      }

      if (section.strumming) {
        html += `<div class="strumming-row"><strong>Strumming:</strong> ${esc(section.strumming)}</div>`;
      }

      if (section.instructions) {
        html += `<div class="instructions-row">${esc(section.instructions)}</div>`;
      }

      html += `</div>`;
    }

    html += `<div class="json-toggle">`;
    html += `<button id="json-toggle-btn">Show JSON</button>`;
    html += `<div id="json-raw" class="json-raw hidden">${esc(JSON.stringify(data, null, 2))}</div>`;
    html += `</div>`;

    outputEl.innerHTML = html;
    outputEl.classList.remove("hidden");

    document.getElementById("download-btn").addEventListener("click", () => {
      const filename = slugify(data.title || "tabs") + ".tabs.json";
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    });

    document.getElementById("json-toggle-btn").addEventListener("click", () => {
      const raw = document.getElementById("json-raw");
      const togBtn = document.getElementById("json-toggle-btn");
      raw.classList.toggle("hidden");
      togBtn.textContent = raw.classList.contains("hidden")
        ? "Show JSON"
        : "Hide JSON";
    });

    for (const link of outputEl.querySelectorAll(".arrangement a[href^='#section-']")) {
      link.addEventListener("click", (e) => {
        e.preventDefault();
        const target = document.querySelector(link.getAttribute("href"));
        if (target) {
          target.scrollIntoView({ behavior: "smooth", block: "start" });
          target.classList.add("section-highlight");
          setTimeout(() => target.classList.remove("section-highlight"), 1500);
        }
      });
    }
  }

  const STRINGS = [
    { label: "e", idx: 5 },
    { label: "B", idx: 4 },
    { label: "G", idx: 3 },
    { label: "D", idx: 2 },
    { label: "A", idx: 1 },
    { label: "E", idx: 0 },
  ];

  const MAX_PER_ROW = 8;

  function renderChordTabs(chords) {
    let html = "";
    for (let offset = 0; offset < chords.length; offset += MAX_PER_ROW) {
      const batch = chords.slice(offset, offset + MAX_PER_ROW);
      html += buildTabBlock(batch);
    }
    return html;
  }

  function buildTabBlock(chords) {
    const colWidths = chords.map((chord) => {
      let maxW = chord.name ? chord.name.length : 1;
      for (const s of STRINGS) {
        const f = chord.frets?.[s.idx];
        const len = f == null ? 1 : String(f).length;
        if (len > maxW) maxW = len;
      }
      return maxW + 4;
    });

    const lines = [];

    for (const s of STRINGS) {
      let line = `<span class="str-label">${s.label}|</span>`;
      for (let c = 0; c < chords.length; c++) {
        const raw = chords[c].frets?.[s.idx];
        const fretStr = raw == null ? "-" : String(raw);
        const pad = colWidths[c] - fretStr.length;
        const before = Math.floor(pad / 2);
        const after = Math.ceil(pad / 2);

        line += `<span class="dash">${"─".repeat(before)}</span>`;
        if (fretStr === "-" || fretStr === "x") {
          line += `<span class="dash">${fretStr === "-" ? "─" : "x"}</span>`;
        } else {
          line += `<span class="fret">${esc(fretStr)}</span>`;
        }
        line += `<span class="dash">${"─".repeat(after)}</span>`;
      }
      line += `<span class="dash">──|</span>`;
      lines.push(line);
    }

    let nameLine = "  ";
    for (let c = 0; c < chords.length; c++) {
      const name = chords[c].name || "";
      const pad = colWidths[c] - name.length;
      const before = Math.floor(pad / 2);
      const after = Math.ceil(pad / 2);
      nameLine += " ".repeat(before + 1);
      nameLine += `<span class="chord-label">${esc(name)}</span>`;
      nameLine += " ".repeat(after + 1);
    }
    lines.push(nameLine);

    return `<div class="tab-block"><div class="tab-lines">${lines.join("\n")}</div></div>`;
  }
});
