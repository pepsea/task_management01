import { api } from "./api.js";
import { addDays, toInputValue } from "./dates.js";
import { el, isWebUrl } from "./ui.js";

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
  const linkList = document.getElementById("task-links");

  // リンク入力の 1 行（URL・表示名・開く・削除）
  function linkRow(link = { url: "", label: "" }) {
    const url = el("input", { type: "url", class: "link-url", placeholder: "https://…", value: link.url, "aria-label": "URL" });
    const label = el("input", { class: "link-label", placeholder: "表示名（任意）", value: link.label, "aria-label": "表示名" });
    const open = el("a", { class: "link-open", target: "_blank", rel: "noopener noreferrer", title: "新しいタブで開く" }, "開く");
    const syncOpen = () => {
      const valid = isWebUrl(url.value.trim());
      if (valid) open.setAttribute("href", url.value.trim());
      else open.removeAttribute("href");
      open.classList.toggle("disabled", !valid);
    };
    url.addEventListener("input", syncOpen);
    syncOpen();
    const row = el("li", {}, url, label, open,
      el("button", { type: "button", class: "danger", "aria-label": "このリンクを削除", onclick: () => row.remove() }, "×"));
    return row;
  }

  function readLinks() {
    return [...linkList.querySelectorAll("li")]
      .map((li) => ({
        url: li.querySelector(".link-url").value.trim(),
        label: li.querySelector(".link-label").value.trim(),
      }))
      .filter((link) => link.url);
  }

  document.getElementById("task-link-add").addEventListener("click", () => {
    const row = linkRow();
    linkList.append(row);
    row.querySelector(".link-url").focus();
  });
  // 登録済みの領域と関連項目の名前（互いに独立）
  let areaNames = [];
  let relatedNames = [];

  function fillAreaOptions(current) {
    const names = [...areaNames];
    // 登録から消えた値のタスクを編集するときも、今の値を選べるように残す
    if (current && !names.includes(current)) names.push(current);
    field("area").replaceChildren(
      el("option", { value: "" }, "（選択してください）"),
      ...names.map((n) => el("option", { value: n }, n)),
    );
    field("area").value = current ?? "";
  }

  function fillRelatedOptions(current) {
    const names = [...relatedNames];
    if (current && !names.includes(current)) names.push(current);
    field("related").replaceChildren(
      el("option", { value: "" }, "（なし）"),
      ...names.map((n) => el("option", { value: n }, n)),
    );
    field("related").value = current ?? "";
  }


  function open({ task = null, defaults = {} } = {}) {
    editing = task;
    ideaId = task ? task.idea_id : (defaults.idea_id ?? null);
    const values = task ?? {
      area: "", related: "", title: "", priority: "mid", done: false, memo: "", ...defaultTimes(), ...defaults,
    };
    fillAreaOptions(values.area);
    fillRelatedOptions(values.related);
    for (const name of ["title", "start_at", "due_at", "priority", "memo"]) {
      field(name).value = values[name] ?? "";
    }
    field("done").checked = Boolean(values.done);
    linkList.replaceChildren(...(values.links ?? []).map(linkRow));
    heading.textContent = task ? "タスクを編集" : "タスクを追加";
    deleteButton.hidden = !task;
    errorBox.textContent = areaNames.length ? "" : "領域が未登録です。先に「⚙ 登録」画面で領域を登録してください";
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
      memo: field("memo").value,
      links: readLinks(),
    };
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = readForm();
    if (!payload.area || !payload.title) {
      errorBox.textContent = "領域とタスク名は必須です";
      return;
    }
    const badLink = payload.links.find((link) => !isWebUrl(link.url));
    if (badLink) {
      errorBox.textContent = `リンクは http:// または https:// で始まる URL にしてください（${badLink.url}）`;
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
    areaNames = areas.map((a) => a.name);
    relatedNames = related.map((r) => r.name);
  }

  return { open, setOptions };
}
