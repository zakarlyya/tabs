document.addEventListener("DOMContentLoaded", () => {
  const STRINGS_DISPLAY = [
    { name: "high e", short: "e", idx: 5 },
    { name: "B", short: "B", idx: 4 },
    { name: "G", short: "G", idx: 3 },
    { name: "D", short: "D", idx: 2 },
    { name: "A", short: "A", idx: 1 },
    { name: "low E", short: "E", idx: 0 },
  ];

  const FINGERS = [
    { value: "", label: "\u2014" },
    { value: "T", label: "Thumb" },
    { value: "1", label: "Index" },
    { value: "2", label: "Middle" },
    { value: "3", label: "Ring" },
    { value: "4", label: "Pinky" },
  ];

  const FINGER_CHAR = { T: "T", "1": "I", "2": "M", "3": "R", "4": "P" };

  let sequence = [];
  let editIndex = -1;

  const saved = localStorage.getItem("tab_editor_sequence");
  if (saved) {
    try {
      sequence = JSON.parse(saved);
    } catch {}
  }

  const grid = document.getElementById("string-grid");
  const nameInput = document.getElementById("chord-name");
  const addBtn = document.getElementById("add-btn");
  const updateBtn = document.getElementById("update-btn");
  const cancelBtn = document.getElementById("cancel-btn");
  const clearBtn = document.getElementById("clear-btn");
  const copyBtn = document.getElementById("copy-btn");

  buildGrid();
  renderAll();

  addBtn.addEventListener("click", () => {
    sequence.push(readBuilder());
    save();
    clearBuilder();
    renderAll();
  });

  updateBtn.addEventListener("click", () => {
    if (editIndex < 0) return;
    sequence[editIndex] = readBuilder();
    editIndex = -1;
    save();
    clearBuilder();
    setEditMode(false);
    renderAll();
  });

  cancelBtn.addEventListener("click", () => {
    editIndex = -1;
    clearBuilder();
    setEditMode(false);
    renderAll();
  });

  clearBtn.addEventListener("click", () => {
    if (sequence.length && !confirm("Clear all chords?")) return;
    sequence = [];
    editIndex = -1;
    save();
    clearBuilder();
    setEditMode(false);
    renderAll();
  });

  copyBtn.addEventListener("click", copyTabText);

  nameInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      if (editIndex >= 0) updateBtn.click();
      else addBtn.click();
    }
  });

  function buildGrid() {
    const optionsHtml = FINGERS.map(
      (f) => `<option value="${f.value}">${f.label}</option>`
    ).join("");

    for (const s of STRINGS_DISPLAY) {
      const row = document.createElement("div");
      row.className = "string-row";
      row.innerHTML =
        `<span class="sr-name">${s.name}</span>` +
        `<input type="text" class="fret-input" data-idx="${s.idx}" placeholder="x" maxlength="2" />` +
        `<select class="finger-select" data-idx="${s.idx}">${optionsHtml}</select>`;
      grid.appendChild(row);
    }
  }

  function readBuilder() {
    const name = nameInput.value.trim() || "?";
    const strings = Array.from({ length: 6 }, () => ({
      fret: "x",
      finger: "",
    }));

    for (const inp of grid.querySelectorAll(".fret-input")) {
      const idx = +inp.dataset.idx;
      const v = inp.value.trim().toLowerCase();
      strings[idx].fret =
        v === "" || v === "x" ? "x" : isNaN(+v) ? "x" : +v;
    }
    for (const sel of grid.querySelectorAll(".finger-select")) {
      strings[+sel.dataset.idx].finger = sel.value;
    }
    return { name, strings };
  }

  function loadBuilder(chord) {
    nameInput.value = chord.name === "?" ? "" : chord.name;
    for (const inp of grid.querySelectorAll(".fret-input")) {
      const s = chord.strings[+inp.dataset.idx];
      inp.value = s.fret === "x" ? "x" : String(s.fret);
    }
    for (const sel of grid.querySelectorAll(".finger-select")) {
      sel.value = chord.strings[+sel.dataset.idx].finger || "";
    }
  }

  function clearBuilder() {
    nameInput.value = "";
    for (const inp of grid.querySelectorAll(".fret-input")) inp.value = "";
    for (const sel of grid.querySelectorAll(".finger-select")) sel.value = "";
  }

  function setEditMode(on) {
    addBtn.classList.toggle("hidden", on);
    updateBtn.classList.toggle("hidden", !on);
    cancelBtn.classList.toggle("hidden", !on);
  }

  function save() {
    localStorage.setItem("tab_editor_sequence", JSON.stringify(sequence));
  }

  function renderAll() {
    renderSequenceList();
    renderTabOutput();
  }

  function renderSequenceList() {
    const list = document.getElementById("sequence-list");
    if (!sequence.length) {
      list.innerHTML =
        '<div class="empty-state">No chords yet. Build one above and add it.</div>';
      return;
    }

    let html = "";
    for (let i = 0; i < sequence.length; i++) {
      const c = sequence[i];
      const fretsStr = c.strings.map((s) => s.fret).join(" ");
      const editing = i === editIndex;
      html += `<div class="seq-item${editing ? " seq-editing" : ""}" data-i="${i}">
        <span class="seq-num">${i + 1}</span>
        <span class="seq-name">${esc(c.name)}</span>
        <span class="seq-frets">${esc(fretsStr)}</span>
        <span class="seq-fingers">${c.strings.map((s) => FINGER_CHAR[s.finger] || "\u00b7").join("")}</span>
        <div class="seq-btns">
          <button class="sq-btn" data-act="edit" data-i="${i}" title="Edit">&#9998;</button>
          <button class="sq-btn" data-act="dup" data-i="${i}" title="Duplicate">&#10697;</button>
          <button class="sq-btn" data-act="up" data-i="${i}" title="Move up" ${i === 0 ? "disabled" : ""}>&uarr;</button>
          <button class="sq-btn" data-act="down" data-i="${i}" title="Move down" ${i === sequence.length - 1 ? "disabled" : ""}>&darr;</button>
          <button class="sq-btn sq-danger" data-act="rm" data-i="${i}" title="Remove">&times;</button>
        </div>
      </div>`;
    }
    list.innerHTML = html;

    for (const btn of list.querySelectorAll("[data-act]")) {
      btn.addEventListener("click", onSeqAction);
    }
  }

  function onSeqAction(e) {
    const act = e.currentTarget.dataset.act;
    const i = +e.currentTarget.dataset.i;

    if (act === "edit") {
      editIndex = i;
      loadBuilder(sequence[i]);
      setEditMode(true);
      renderAll();
      nameInput.focus();
    } else if (act === "dup") {
      sequence.splice(i + 1, 0, JSON.parse(JSON.stringify(sequence[i])));
      save();
      renderAll();
    } else if (act === "up" && i > 0) {
      [sequence[i - 1], sequence[i]] = [sequence[i], sequence[i - 1]];
      if (editIndex === i) editIndex--;
      else if (editIndex === i - 1) editIndex++;
      save();
      renderAll();
    } else if (act === "down" && i < sequence.length - 1) {
      [sequence[i], sequence[i + 1]] = [sequence[i + 1], sequence[i]];
      if (editIndex === i) editIndex++;
      else if (editIndex === i + 1) editIndex--;
      save();
      renderAll();
    } else if (act === "rm") {
      sequence.splice(i, 1);
      if (editIndex === i) {
        editIndex = -1;
        clearBuilder();
        setEditMode(false);
      } else if (editIndex > i) {
        editIndex--;
      }
      save();
      renderAll();
    }
  }

  function renderTabOutput() {
    const wrap = document.getElementById("tab-output");
    const target = document.getElementById("rendered-tab");
    if (!sequence.length) {
      wrap.classList.add("hidden");
      return;
    }
    wrap.classList.remove("hidden");

    const MAX = 8;
    let html = "";
    for (let off = 0; off < sequence.length; off += MAX) {
      html += buildBlock(sequence.slice(off, off + MAX));
    }
    target.innerHTML = html;
  }

  function cellText(stringData) {
    const fret = String(stringData.fret);
    const fc = FINGER_CHAR[stringData.finger] || "";
    return fret + fc;
  }

  function buildBlock(chords) {
    const colW = chords.map((c) => {
      let w = c.name.length || 1;
      for (const s of STRINGS_DISPLAY) {
        const len = cellText(c.strings[s.idx]).length;
        if (len > w) w = len;
      }
      return w + 4;
    });

    const hasFingers = chords.some((c) => c.strings.some((s) => s.finger));
    const lines = [];

    for (const s of STRINGS_DISPLAY) {
      let line = `<span class="str-label">${s.short}|</span>`;
      for (let ci = 0; ci < chords.length; ci++) {
        const sd = chords[ci].strings[s.idx];
        const fret = String(sd.fret);
        const fc = FINGER_CHAR[sd.finger] || "";
        const token = fret + fc;
        const pad = colW[ci] - token.length;
        const bef = Math.floor(pad / 2);
        const aft = Math.ceil(pad / 2);

        line += `<span class="dash">${"\u2500".repeat(bef)}</span>`;
        if (fret === "x") {
          line += `<span class="dash">x</span>`;
        } else {
          line += `<span class="fret">${esc(fret)}</span>`;
        }
        if (fc) {
          line += `<span class="finger">${fc}</span>`;
        }
        line += `<span class="dash">${"\u2500".repeat(aft)}</span>`;
      }
      line += `<span class="dash">\u2500\u2500|</span>`;
      lines.push(line);
    }

    let nameLine = "  ";
    for (let ci = 0; ci < chords.length; ci++) {
      const n = chords[ci].name;
      const pad = colW[ci] - n.length;
      nameLine +=
        " ".repeat(Math.floor(pad / 2) + 1) +
        `<span class="chord-label">${esc(n)}</span>` +
        " ".repeat(Math.ceil(pad / 2) + 1);
    }
    lines.push(nameLine);

    if (hasFingers) {
      lines.push(
        `<span class="finger-key">T=Thumb  I=Index  M=Middle  R=Ring  P=Pinky</span>`
      );
    }

    return `<div class="tab-block"><div class="tab-lines">${lines.join("\n")}</div></div>`;
  }

  function copyTabText() {
    if (!sequence.length) return;

    const colW = sequence.map((c) => {
      let w = c.name.length || 1;
      for (const s of STRINGS_DISPLAY) {
        const len = cellText(c.strings[s.idx]).length;
        if (len > w) w = len;
      }
      return w + 4;
    });

    let text = "";
    for (const s of STRINGS_DISPLAY) {
      let line = s.short + "|";
      for (let ci = 0; ci < sequence.length; ci++) {
        const token = cellText(sequence[ci].strings[s.idx]);
        const pad = colW[ci] - token.length;
        line +=
          "-".repeat(Math.floor(pad / 2)) +
          token +
          "-".repeat(Math.ceil(pad / 2));
      }
      text += line + "--|" + "\n";
    }

    let names = "  ";
    for (let ci = 0; ci < sequence.length; ci++) {
      const n = sequence[ci].name;
      const pad = colW[ci] - n.length;
      names +=
        " ".repeat(Math.floor(pad / 2) + 1) +
        n +
        " ".repeat(Math.ceil(pad / 2) + 1);
    }
    text += names + "\n";

    const hasFingers = sequence.some((c) => c.strings.some((s) => s.finger));
    if (hasFingers) {
      text += "T=Thumb  I=Index  M=Middle  R=Ring  P=Pinky\n";
    }

    navigator.clipboard.writeText(text).then(() => {
      copyBtn.textContent = "Copied!";
      setTimeout(() => {
        copyBtn.textContent = "Copy as Text";
      }, 1500);
    });
  }

  function esc(str) {
    const d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
  }
});
