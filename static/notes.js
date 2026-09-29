import { api } from "./api.js";
import { createBlockEditor } from "./blockEditor.js";
import { formatDateLabel, formatStamp } from "./dates.js";
import { copyNote, exportNote } from "./noteExport.js";
import { createSortable } from "./sortable.js";
import { el, tagChip, toast } from "./ui.js";

const AUTOSAVE_MS = 800;
const SEARCH_MS = 300;

const list = document.getElementById("note-list");
const search = document.getElementById("note-search");
const tagFilter = document.getElementById("note-tag-filter");
const editorPane = document.getElementById("note-editor");
const placeholder = document.getElementById("note-placeholder");
const status = document.getElementById("note-status");
const stamp = document.getElementById("note-stamp");
const tagChips = document.getElementById("note-tags");
const tagInput = document.getElementById("note-tag-input");
const dateInput = document.getElementById("note-date");
const titleInput = document.getElementById("note-title");

const titleOf = (note) => note.title || "無題";

let notes = [];
let selectedId = null;
let selectedTags = [];
let saveTimer = null;
let searchTimer = null;

const editor = createBlockEditor(document.getElementById("note-body"), {
  onInput: () => scheduleSave(),
});

const sortable = createSortable({
  list,
  getItems: () => notes,
  setItems: (items) => {
    notes = items;
    renderList();
  },
  groupOf: (note) => note.pinned,
  onReorder: async (ids) => {
    try {
      await api.reorderNotes(ids);
    } catch (err) {
      toast(err.message);
    }
    await refresh();
  },
});

function setEditorVisible(visible) {
  editorPane.hidden = !visible;
  placeholder.hidden = visible;
}

function renderList() {
  if (!notes.length) {
    const filtered = search.value.trim() || tagFilter.value;
    list.replaceChildren(el("li", { class: "empty" }, filtered ? "該当なし" : "メモはまだありません"));
    return;
  }
  list.replaceChildren(...notes.map((note) =>
    el("li", {
      class: `${note.id === selectedId ? "selected" : ""}${note.pinned ? " prioritized" : ""}`,
      ...sortable(note),
      onclick: () => (note.id === selectedId ? close() : select(note.id)),
    },
      el("span", { class: "drag-handle", title: "ドラッグで並べ替え", "aria-hidden": "true" }, "⋮⋮"),
      el("button", {
        type: "button",
        class: `star${note.pinned ? " on" : ""}`,
        title: note.pinned ? "ピン留めを外す" : "ピン留めする（先頭に固定）",
        "aria-pressed": note.pinned ? "true" : "false",
        onclick: (e) => {
          e.stopPropagation();
          togglePin(note);
        },
      }, note.pinned ? "★" : "☆"),
      el("span", { class: `idea-title${note.title ? "" : " untitled"}`, title: titleOf(note) }, titleOf(note)),
      note.tags.length ? el("span", { class: "tag-chips" }, note.tags.map((t) => tagChip(t))) : null,
      el("span", { class: "note-list-date", title: note.note_date }, formatDateLabel(note.note_date)))));
}

async function loadTags() {
  const tags = await api.listTags();
  const selected = tagFilter.value;
  tagFilter.replaceChildren(
    el("option", { value: "" }, "すべてのタグ"),
    ...tags.map((t) => el("option", { value: t.name }, t.name)),
  );
  tagFilter.value = tags.some((t) => t.name === selected) ? selected : "";
  document.getElementById("tag-options").replaceChildren(...tags.map((t) => el("option", { value: t.name })));
}

async function refresh() {
  try {
    await loadTags();
    // 一覧はいつもドラッグで決めた順（★ は先頭）
    notes = await api.listNotes(search.value.trim(), tagFilter.value, false, "manual");
    renderList();
  } catch (err) {
    toast(err.message);
  }
}

function showMeta(note) {
  stamp.textContent = `作成 ${formatStamp(note.created_at)} ・ 更新 ${formatStamp(note.updated_at)}`;
}

async function save() {
  saveTimer = null;
  if (selectedId === null) return;
  try {
    const updated = await api.updateNote(selectedId, { title: titleInput.value.trim(), body: editor.value() });
    status.textContent = "保存済み";
    showMeta(updated);
    const index = notes.findIndex((n) => n.id === updated.id);
    if (index >= 0 && notes[index].title !== updated.title) {
      notes[index] = updated;
      renderList();
    }
  } catch {
    // 次の入力で scheduleSave が再び呼ばれ、再試行される
    status.textContent = "保存失敗（次の入力で再試行します）";
  }
}

function scheduleSave() {
  if (selectedId === null) return;
  status.textContent = "編集中…";
  clearTimeout(saveTimer);
  saveTimer = setTimeout(save, AUTOSAVE_MS);
}

async function flushSave() {
  if (saveTimer !== null) {
    clearTimeout(saveTimer);
    await save();
  }
}

function renderSelectedTags() {
  tagChips.replaceChildren(...selectedTags.map((tag) =>
    tagChip(tag, { onRemove: () => saveTags(selectedTags.filter((t) => t.name !== tag.name).map((t) => t.name)) })));
}

async function saveTags(names) {
  if (selectedId === null) return;
  try {
    const updated = await api.updateNote(selectedId, { tags: names });
    selectedTags = updated.tags;
    renderSelectedTags();
    await refresh();
  } catch (err) {
    toast(err.message);
  }
}

async function select(id, { startWriting = false } = {}) {
  await flushSave();
  try {
    const note = await api.getNote(id);
    selectedId = note.id;
    selectedTags = note.tags;
    renderSelectedTags();
    tagInput.value = "";
    status.textContent = "";
    showMeta(note);
    dateInput.value = note.note_date;
    titleInput.value = note.title;
    setEditorVisible(true);
    editor.setValue(note.body);
    if (startWriting) {
      titleInput.focus();
    }
    renderList();
  } catch (err) {
    toast(err.message);
  }
}

async function close() {
  await flushSave();
  selectedId = null;
  setEditorVisible(false);
  renderList();
}

async function togglePin(note) {
  try {
    await api.updateNote(note.id, { pinned: !note.pinned });
    await refresh();
  } catch (err) {
    toast(err.message);
  }
}

document.getElementById("note-add").addEventListener("click", async () => {
  try {
    const note = await api.createNote({ body: "" });
    search.value = "";
    tagFilter.value = "";
    await refresh();
    await select(note.id, { startWriting: true });
  } catch (err) {
    toast(err.message);
  }
});

document.getElementById("note-archive").addEventListener("click", async () => {
  if (selectedId === null) return;
  await flushSave();
  try {
    const note = await api.updateNote(selectedId, { archived: true });
    toast(`「${titleOf(note)}」をアーカイブしました`);
    selectedId = null;
    setEditorVisible(false);
    await refresh();
  } catch (err) {
    toast(err.message);
  }
});

document.getElementById("note-delete").addEventListener("click", async () => {
  const note = notes.find((n) => n.id === selectedId);
  if (!note || !confirm(`「${titleOf(note)}」を削除しますか？`)) return;
  clearTimeout(saveTimer);
  saveTimer = null;
  try {
    await api.deleteNote(selectedId);
    selectedId = null;
    setEditorVisible(false);
    await refresh();
  } catch (err) {
    toast(err.message);
  }
});

document.getElementById("note-close").addEventListener("click", close);

document.getElementById("note-copy").addEventListener("click", () => {
  if (selectedId === null) return;
  // 画面に表示中の内容をその場でコピーする（サーバーからの読み込みを待つと、
  // ブラウザによってはボタンを押した直後の扱いが切れてコピーが許可されないため）
  copyNote({ title: titleInput.value.trim(), body: editor.value(), note_date: dateInput.value });
  flushSave();
});

document.getElementById("note-export").addEventListener("click", async () => {
  if (selectedId === null) return;
  // 入力中の内容を保存してから、最新の内容で書き出す
  await flushSave();
  try {
    exportNote(await api.getNote(selectedId));
  } catch (err) {
    toast(err.message);
  }
});

// 書式ボタン（文字を選んでから押す）。蛍光ペンは ==文==、文字色は <span style="color:…">文</span>
const TEXT_COLORS = [
  { name: "赤", value: "#dc2626" },
  { name: "青", value: "#2563eb" },
  { name: "緑", value: "#16a34a" },
  { name: "橙", value: "#d97706" },
  { name: "紫", value: "#7c3aed" },
];
const formatBar = document.getElementById("format-bar");
formatBar.querySelector(".format-colors").replaceChildren(...TEXT_COLORS.map((color) => el("button", {
  type: "button",
  class: "format-color",
  "data-format": "color",
  "data-color": color.value,
  title: `文字を${color.name}にする`,
  "aria-label": `文字を${color.name}にする`,
  style: `background:${color.value}`,
})));
// ボタンを押しても編集中のブロックからフォーカスを外さない（外れると選んだ文字が分からなくなる）
formatBar.addEventListener("mousedown", (e) => {
  if (e.target.closest("button")) e.preventDefault();
});
formatBar.addEventListener("click", (e) => {
  const button = e.target.closest("button[data-format]");
  if (!button) return;
  const [before, after] = button.dataset.format === "mark"
    ? ["==", "=="]
    : [`<span style="color:${button.dataset.color}">`, "</span>"];
  if (!editor.wrapSelection(before, after)) {
    toast("本文のブロックをクリックして編集し、色を付けたい文字を選んでから押してください");
  }
});

titleInput.addEventListener("input", scheduleSave);
titleInput.addEventListener("keydown", (e) => {
  // タイトルで Enter を押したら本文を書き始める
  if (e.key === "Enter" && !e.isComposing && e.keyCode !== 229) {
    e.preventDefault();
    editor.startWriting();
  }
});

// 今の並び順を、日付の新しい順に並べ直す（押したときだけ）
document.getElementById("note-sort-date").addEventListener("click", async () => {
  if (!confirm("メモの並び順を、日付の新しい順に並べ直しますか？\n（ドラッグで決めた並び順は置き換わります）")) return;
  try {
    await api.sortNotesByDate();
    await refresh();
    toast("日付の新しい順に並べ直しました");
  } catch (err) {
    toast(err.message);
  }
});

dateInput.addEventListener("change", async () => {
  if (selectedId === null) return;
  if (!dateInput.value) {
    // 日付は空にできないので、元の日付に戻す
    const note = notes.find((n) => n.id === selectedId);
    if (note) dateInput.value = note.note_date;
    return;
  }
  try {
    const updated = await api.updateNote(selectedId, { note_date: dateInput.value });
    showMeta(updated);
    status.textContent = "保存済み";
    await refresh();
  } catch (err) {
    toast(err.message);
  }
});

tagInput.addEventListener("keydown", (e) => {
  // 日本語入力の変換確定の Enter では追加しない
  if (e.key !== "Enter" || e.isComposing || e.keyCode === 229) return;
  e.preventDefault();
  const name = tagInput.value.trim();
  if (!name) return;
  tagInput.value = "";
  if (selectedTags.some((t) => t.name === name)) return;
  saveTags([...selectedTags.map((t) => t.name), name]);
});

search.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(refresh, SEARCH_MS);
});
tagFilter.addEventListener("change", refresh);

// ページを離れるときに未保存の入力を送る（keepalive でページが閉じても送信を続ける）
window.addEventListener("pagehide", () => {
  if (saveTimer === null || selectedId === null) return;
  fetch(`/api/notes/${selectedId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: titleInput.value.trim(), body: editor.value() }),
    keepalive: true,
  });
});

refresh();
