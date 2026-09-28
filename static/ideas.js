import { api } from "./api.js";
import { formatStamp } from "./dates.js";
import { el, tagChip, toast } from "./ui.js";

const AUTOSAVE_MS = 800;
const SEARCH_MS = 300;

export function initIdeas({ onMakeTask }) {
  const list = document.getElementById("idea-list");
  const search = document.getElementById("idea-search");
  const editor = document.getElementById("idea-editor");
  const titleInput = document.getElementById("idea-title");
  const bodyInput = document.getElementById("idea-body");
  const status = document.getElementById("idea-status");
  const tagFilter = document.getElementById("idea-tag-filter");
  const tagChips = document.getElementById("idea-tags");
  const tagInput = document.getElementById("idea-tag-input");

  let ideas = [];
  let selectedId = null;
  let saveTimer = null;
  let searchTimer = null;
  let selectedTags = [];

  function renderList() {
    if (!ideas.length) {
      const filtered = search.value.trim() || tagFilter.value;
      list.replaceChildren(el("li", { class: "empty" }, filtered ? "該当なし" : "アイディアはまだありません"));
      return;
    }
    list.replaceChildren(...ideas.map((idea) =>
      el("li", { class: idea.id === selectedId ? "selected" : "", onclick: () => select(idea.id) },
        el("span", { class: "idea-title", title: idea.title }, idea.title),
        el("span", { class: "tag-chips" }, idea.tags.map((t) => tagChip(t))),
        idea.task_count > 0 ? el("span", { class: "badge", title: "タスク化済み" }, "✓") : null)));
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
      ideas = await api.listIdeas(search.value.trim(), tagFilter.value);
      renderList();
    } catch (err) {
      toast(err.message);
    }
  }

  function renderSelectedTags() {
    tagChips.replaceChildren(...selectedTags.map((tag) =>
      tagChip(tag, { onRemove: () => saveTags(selectedTags.filter((t) => t.name !== tag.name).map((t) => t.name)) })));
  }

  async function saveTags(names) {
    if (selectedId === null) return;
    try {
      const updated = await api.updateIdea(selectedId, { tags: names });
      selectedTags = updated.tags;
      renderSelectedTags();
      await refresh();
    } catch (err) {
      toast(err.message);
    }
  }

  async function save() {
    saveTimer = null;
    if (selectedId === null) return;
    const title = titleInput.value.trim();
    if (!title) {
      status.textContent = "タイトルは必須です（未保存）";
      return;
    }
    try {
      const updated = await api.updateIdea(selectedId, { title, body: bodyInput.value });
      status.textContent = "保存済み";
      const index = ideas.findIndex((i) => i.id === updated.id);
      if (index >= 0) {
        ideas[index] = updated;
        renderList();
      }
    } catch {
      // 次の入力で scheduleSave が再び呼ばれ、再試行される
      status.textContent = "保存失敗（次の入力で再試行します）";
    }
  }

  function scheduleSave() {
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

  async function select(id) {
    await flushSave();
    try {
      const idea = await api.getIdea(id);
      selectedId = idea.id;
      titleInput.value = idea.title;
      bodyInput.value = idea.body;
      document.getElementById("idea-stamp").textContent =
        `思いつき ${formatStamp(idea.created_at)} ・ 更新 ${formatStamp(idea.updated_at)}`;
      selectedTags = idea.tags;
      renderSelectedTags();
      tagInput.value = "";
      status.textContent = "";
      editor.hidden = false;
      renderList();
    } catch (err) {
      toast(err.message);
    }
  }

  async function reveal(id) {
    search.value = "";
    tagFilter.value = "";
    await refresh();
    await select(id);
  }

  titleInput.addEventListener("input", scheduleSave);
  bodyInput.addEventListener("input", scheduleSave);
  tagFilter.addEventListener("change", refresh);
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

  document.getElementById("add-idea").addEventListener("click", async () => {
    try {
      const idea = await api.createIdea({ title: "新しいアイディア", body: "" });
      await reveal(idea.id);
      titleInput.select();
      titleInput.focus();
    } catch (err) {
      toast(err.message);
    }
  });

  document.getElementById("idea-delete").addEventListener("click", async () => {
    if (selectedId === null || !confirm(`「${titleInput.value}」を削除しますか？`)) return;
    clearTimeout(saveTimer);
    saveTimer = null;
    try {
      await api.deleteIdea(selectedId);
      selectedId = null;
      editor.hidden = true;
      await refresh();
    } catch (err) {
      toast(err.message);
    }
  });

  document.getElementById("idea-archive").addEventListener("click", async () => {
    if (selectedId === null) return;
    await flushSave();
    try {
      await api.updateIdea(selectedId, { archived: true });
      toast(`「${titleInput.value}」をアーカイブしました`);
      selectedId = null;
      editor.hidden = true;
      await refresh();
    } catch (err) {
      toast(err.message);
    }
  });

  document.getElementById("idea-to-task").addEventListener("click", async () => {
    if (selectedId === null) return;
    await flushSave();
    onMakeTask({ id: selectedId, title: titleInput.value.trim() });
  });

  refresh();
  return { refresh, reveal };
}
