import { api } from "./api.js";
import { toInputValue } from "./dates.js";

export function initDecisionForm({ onSaved }) {
  const dialog = document.getElementById("decision-dialog");
  const form = document.getElementById("decision-form");
  const heading = document.getElementById("decision-form-title");
  const errorBox = document.getElementById("decision-form-error");
  const deleteButton = document.getElementById("decision-delete");
  const field = (name) => form.elements.namedItem(name);

  let editing = null;

  function open({ decision = null } = {}) {
    editing = decision;
    field("title").value = decision?.title ?? "";
    field("date").value = decision?.date ?? toInputValue(new Date()).slice(0, 10);
    field("time").value = decision?.time ?? "";
    heading.textContent = decision ? "ディシジョンポイントを編集" : "ディシジョンポイントを追加";
    deleteButton.hidden = !decision;
    errorBox.textContent = "";
    dialog.showModal();
    field("title").focus();
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      title: field("title").value.trim(),
      date: field("date").value,
      time: field("time").value || null,
    };
    if (!payload.title || !payload.date) {
      errorBox.textContent = "名前と日付は必須です";
      return;
    }
    try {
      if (editing) await api.updateDecision(editing.id, payload);
      else await api.createDecision(payload);
      dialog.close();
      await onSaved();
    } catch (err) {
      errorBox.textContent = err.message;
    }
  });

  deleteButton.addEventListener("click", async () => {
    if (!editing || !confirm(`「${editing.title}」を削除しますか？`)) return;
    try {
      await api.deleteDecision(editing.id);
      dialog.close();
      await onSaved();
    } catch (err) {
      errorBox.textContent = err.message;
    }
  });

  document.getElementById("decision-cancel").addEventListener("click", () => dialog.close());

  return { open };
}
