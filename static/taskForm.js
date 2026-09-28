import { api } from "./api.js";
import { addDays, toInputValue } from "./dates.js";
import { el } from "./ui.js";

function defaultTimes() {
  const start = new Date();
  start.setHours(9, 0, 0, 0);
  const due = addDays(start, 7);
  due.setHours(18, 0, 0, 0);
  return { start_at: toInputValue(start), due_at: toInputValue(due) };
}

export function initTaskForm({ onSaved }) {
  const dialog = document.getElementById("task-dialog");
  const form = document.getElementById("task-form");
  const heading = document.getElementById("task-form-title");
  const errorBox = document.getElementById("task-form-error");
  const deleteButton = document.getElementById("task-delete");
  // form.title は HTMLElement の title 属性と衝突するため namedItem で取得する
  const field = (name) => form.elements.namedItem(name);

  let editing = null;
  let ideaId = null;

  function open({ task = null, defaults = {} } = {}) {
    editing = task;
    ideaId = task ? task.idea_id : (defaults.idea_id ?? null);
    const values = task ?? {
      area: "", related: "", title: "", priority: "mid", done: false, ...defaultTimes(), ...defaults,
    };
    for (const name of ["area", "related", "title", "start_at", "due_at", "priority"]) {
      field(name).value = values[name] ?? "";
    }
    field("done").checked = Boolean(values.done);
    heading.textContent = task ? "タスクを編集" : "タスクを追加";
    deleteButton.hidden = !task;
    errorBox.textContent = "";
    dialog.showModal();
    field(values.area ? "title" : "area").focus();
  }

  function readForm() {
    return {
      area: field("area").value.trim(),
      related: field("related").value.trim(),
      title: field("title").value.trim(),
      start_at: field("start_at").value,
      due_at: field("due_at").value,
      priority: field("priority").value,
      done: field("done").checked,
    };
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = readForm();
    if (!payload.area || !payload.title) {
      errorBox.textContent = "領域とタスク名は必須です";
      return;
    }
    if (payload.due_at < payload.start_at) {
      errorBox.textContent = "期限は開始日時以降にしてください";
      return;
    }
    try {
      const saved = editing
        ? await api.updateTask(editing.id, payload)
        : await api.createTask({ ...payload, idea_id: ideaId });
      dialog.close();
      onSaved(saved, { deleted: false });
    } catch (err) {
      errorBox.textContent = err.message;
    }
  });

  deleteButton.addEventListener("click", async () => {
    if (!editing || !confirm(`「${editing.title}」を削除しますか？`)) return;
    try {
      await api.deleteTask(editing.id);
      dialog.close();
      onSaved(null, { deleted: true });
    } catch (err) {
      errorBox.textContent = err.message;
    }
  });

  document.getElementById("task-cancel").addEventListener("click", () => dialog.close());

  function setOptions({ areas, related }) {
    const fill = (id, values) =>
      document.getElementById(id).replaceChildren(...values.map((v) => el("option", { value: v })));
    fill("area-options", areas);
    fill("related-options", related);
  }

  return { open, setOptions };
}
