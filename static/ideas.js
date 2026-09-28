import { api } from "./api.js";
import { el, toast } from "./ui.js";

const AUTOSAVE_MS = 800;
const SEARCH_MS = 300;

export function initIdeas({ onMakeTask }) {
  const list = document.getElementById("idea-list");
  const search = document.getElementById("idea-search");
  const editor = document.getElementById("idea-editor");
  const titleInput = document.getElementById("idea-title");
  const bodyInput = document.getElementById("idea-body");
  const status = document.getElementById("idea-status");

  let ideas = [];
  let selectedId = null;
  let saveTimer = null;
  let searchTimer = null;

  function renderList() {
    if (!ideas.length) {
      list.replaceChildren(el("li", { class: "empty" }, search.value.trim() ? "該当なし" : "アイディアはまだありません"));
      return;
    }
    list.replaceChildren(...ideas.map((idea) =>
      el("li", { class: idea.id === selectedId ? "selected" : "", onclick: () => select(idea.id) },
        el("span", { class: "idea-title", title: idea.title }, idea.title),
        idea.task_count > 0 ? el("span", { class: "badge", title: "タスク化済み" }, "✓") : null)));
  }

  async function refresh() {
    try {
      ideas = await api.listIdeas(search.value.trim());
      renderList();
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
      status.textContent = "";
      editor.hidden = false;
      renderList();
    } catch (err) {
      toast(err.message);
    }
  }

  async function reveal(id) {
    search.value = "";
    await refresh();
    await select(id);
  }

  titleInput.addEventListener("input", scheduleSave);
  bodyInput.addEventListener("input", scheduleSave);
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

  document.getElementById("idea-to-task").addEventListener("click", async () => {
    if (selectedId === null) return;
    await flushSave();
    onMakeTask({ id: selectedId, title: titleInput.value.trim() });
  });

  refresh();
  return { refresh, reveal };
}
