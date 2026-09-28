import { api } from "./api.js";
import { createBlockEditor } from "./blockEditor.js";
import { formatStamp } from "./dates.js";
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
      el("span", { class: "idea-title", title: note.title }, note.title),
      note.tags.length ? el("span", { class: "tag-chips" }, note.tags.map((t) => tagChip(t))) : null)));
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
    notes = await api.listNotes(search.value.trim(), tagFilter.value);
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
    const updated = await api.updateNote(selectedId, { body: editor.value() });
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
    setEditorVisible(true);
    editor.setValue(note.body);
    if (startWriting) editor.startWriting();
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
    toast(`「${note.title}」をアーカイブしました`);
    selectedId = null;
    setEditorVisible(false);
    await refresh();
  } catch (err) {
    toast(err.message);
  }
});

document.getElementById("note-delete").addEventListener("click", async () => {
  const note = notes.find((n) => n.id === selectedId);
  if (!note || !confirm(`「${note.title}」を削除しますか？`)) return;
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
    body: JSON.stringify({ body: editor.value() }),
    keepalive: true,
  });
});

refresh();
