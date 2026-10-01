import { api } from "./api.js";
import { addDays, toInputValue, todayKey } from "./dates.js";
import { copyPath, el, linkKind } from "./ui.js";

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
    const url = el("input", { class: "link-url", placeholder: "https://…　C:\\…　\\\\サーバー\\…", value: link.url, "aria-label": "URL またはパス" });
    const label = el("input", { class: "link-label", placeholder: "表示名（任意）", value: link.label, "aria-label": "表示名" });
    const open = el("a", { class: "link-open", target: "_blank", rel: "noopener noreferrer", title: "新しいタブで開く" }, "開く");
    // Web は「開く」、パスは「コピー」（ブラウザからは開けないため）
    const syncOpen = () => {
      const value = cleanUrl(url.value);
      const kind = linkKind(value);
      if (kind === "web" || kind === "smb") open.setAttribute("href", value);
      else open.removeAttribute("href");
      open.textContent = kind === "path" ? "コピー" : "開く";
      open.title = kind === "path" ? "パスをコピー" : "新しいタブで開く";
      open.classList.toggle("disabled", !kind);
    };
    open.addEventListener("click", (e) => {
      const value = cleanUrl(url.value);
      if (linkKind(value) !== "path") return;
      e.preventDefault();
      copyPath(value);
    });
    url.addEventListener("input", syncOpen);
    syncOpen();
    const row = el("li", {}, url, label, open,
      el("button", { type: "button", class: "danger", "aria-label": "このリンクを削除", onclick: () => row.remove() }, "×"));
    return row;
  }

  // Windows の「パスのコピー」で付く前後の " を外す
  const cleanUrl = (value) => value.trim().replace(/^"(.*)"$/, "$1").trim();

  function readLinks() {
    return [...linkList.querySelectorAll("li")]
      .map((li) => ({
        url: cleanUrl(li.querySelector(".link-url").value),
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
    for (const name of ["title", "priority", "memo"]) {
      field(name).value = values[name] ?? "";
    }
    // 入力は日付だけ（時刻は保存済みのものをそのまま使う）
    field("start_at").value = values.start_at.slice(0, 10);
    field("due_at").value = values.due_at.slice(0, 10);
    field("done").checked = Boolean(values.done);
    // 新しいタスクは「今日のタスク」をオンにしておく。編集では今の状態
    field("today").checked = task ? task.today_on === todayKey() : true;
    linkList.replaceChildren(...(values.links ?? []).map(linkRow));
    heading.textContent = task ? "タスクを編集" : "タスクを追加";
    deleteButton.hidden = !task;
    errorBox.textContent = areaNames.length ? "" : "領域が未登録です。先に REGISTRATION タブで領域を登録してください";
    dialog.showModal();
    field(values.area ? "title" : "area").focus();
  }

  // 日付に時刻を付ける。編集中は元の時刻、新規は開始 9:00・期限 18:00
  const withTime = (name, time) => `${field(name).value}${editing ? editing[name].slice(10) : time}`;

  function readForm() {
    return {
      area: field("area").value.trim(),
      related: field("related").value.trim(),
      title: field("title").value.trim(),
      start_at: withTime("start_at", "T09:00"),
      due_at: withTime("due_at", "T18:00"),
      priority: field("priority").value,
      done: field("done").checked,
      today_on: field("today").checked ? todayKey() : null,
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
    const badLink = payload.links.find((link) => !linkKind(link.url));
    if (badLink) {
      errorBox.textContent = `リンクは http(s)://、smb://、C:\\…、\\\\サーバー\\…、file:// のいずれかにしてください（${badLink.url}）`;
      return;
    }
    if (payload.due_at.slice(0, 10) < payload.start_at.slice(0, 10)) {
      errorBox.textContent = "期限は開始日以降にしてください";
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
