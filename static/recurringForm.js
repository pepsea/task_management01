import { api } from "./api.js";
import { todayKey } from "./dates.js";
import { el } from "./ui.js";

const WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"];

// 「毎月 25日」「毎月 第2 火曜」「毎週 月曜」
export function ruleLabel(r) {
  if (r.rule === "monthly_day") return `毎月 ${r.day}日`;
  if (r.rule === "monthly_weekday") return `毎月 ${r.nth === 5 ? "最終" : `第${r.nth}`} ${WEEKDAYS[r.weekday]}曜`;
  return `毎週 ${WEEKDAYS[r.weekday]}曜`;
}

/**
 * 定期タスクの一覧と編集のダイアログ。一覧の行をクリックで編集、「＋ 定期タスクを追加」で新規。
 * 保存・削除すると onSaved（ガントの読み直し）を呼ぶ
 */
export function initRecurringForm({ onSaved }) {
  const dialog = document.getElementById("recurring-dialog");
  const listView = document.getElementById("recurring-list-view");
  const list = document.getElementById("recurring-list");
  const form = document.getElementById("recurring-form");
  const heading = document.getElementById("recurring-form-title");
  const errorBox = document.getElementById("recurring-form-error");
  const deleteButton = document.getElementById("recurring-delete");
  const field = (name) => form.elements.namedItem(name);

  let editing = null;
  let areaNames = [];
  let relatedNames = [];

  field("day").replaceChildren(...Array.from({ length: 31 }, (_, i) =>
    el("option", { value: i + 1 }, i + 1 >= 29 ? `${i + 1}日（無い月は月末）` : `${i + 1}日`)));

  function fillSelect(name, names, current, emptyLabel) {
    const options = [...names];
    if (current && !options.includes(current)) options.push(current);
    field(name).replaceChildren(el("option", { value: "" }, emptyLabel), ...options.map((n) => el("option", { value: n }, n)));
    field(name).value = current ?? "";
  }

  // 繰り返しの種類に合わせて、日・第○・曜日の欄を出し分ける
  function syncRuleFields() {
    const rule = field("rule").value;
    for (const label of form.querySelectorAll("[data-for]")) {
      label.hidden = !label.dataset.for.split(" ").includes(rule);
    }
  }
  field("rule").addEventListener("change", syncRuleFields);

  async function showList() {
    form.hidden = true;
    listView.hidden = false;
    try {
      const items = await api.listRecurring();
      list.replaceChildren(...(items.length
        ? items.map((r) => el("li", { onclick: () => showForm(r), title: "クリックで編集" },
          el("span", { class: "recurring-title" }, r.title),
          el("span", { class: "recurring-area" }, r.related ? `${r.area} / ${r.related}` : r.area),
          el("span", { class: "recurring-when" }, ruleLabel(r))))
        : [el("li", { class: "empty" }, "定期タスクはまだありません")]));
    } catch (err) {
      list.replaceChildren(el("li", { class: "empty" }, err.message));
    }
  }

  function showForm(item = null) {
    editing = item;
    const values = item ?? {
      area: "", related: "", title: "", priority: "mid", memo: "", rule: "monthly_day",
      day: new Date().getDate(), nth: 1, weekday: 0, lead_days: 0, start_from: todayKey(),
    };
    fillSelect("area", areaNames, values.area, "（選択してください）");
    fillSelect("related", relatedNames, values.related, "（なし）");
    for (const name of ["title", "priority", "memo", "rule", "lead_days", "start_from"]) field(name).value = values[name];
    field("day").value = String(values.day ?? 1);
    field("nth").value = String(values.nth ?? 1);
    field("weekday").value = String(values.weekday ?? 0);
    syncRuleFields();
    heading.textContent = item ? "定期タスクを編集" : "定期タスクを追加";
    deleteButton.hidden = !item;
    errorBox.textContent = areaNames.length ? "" : "領域が未登録です。先に REGISTRATION タブで領域を登録してください";
    listView.hidden = true;
    form.hidden = false;
    field(values.area ? "title" : "area").focus();
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const rule = field("rule").value;
    const payload = {
      area: field("area").value,
      related: field("related").value,
      title: field("title").value.trim(),
      priority: field("priority").value,
      memo: field("memo").value,
      rule,
      day: rule === "monthly_day" ? Number(field("day").value) : null,
      nth: rule === "monthly_weekday" ? Number(field("nth").value) : null,
      weekday: rule === "monthly_day" ? null : Number(field("weekday").value),
      lead_days: Number(field("lead_days").value),
      start_from: field("start_from").value,
    };
    if (!payload.area || !payload.title) {
      errorBox.textContent = "領域とタスク名は必須です";
      return;
    }
    try {
      if (editing) await api.updateRecurring(editing.id, payload);
      else await api.createRecurring(payload);
      await onSaved();
      await showList();
    } catch (err) {
      errorBox.textContent = err.message;
    }
  });

  deleteButton.addEventListener("click", async () => {
    if (!editing) return;
    if (!confirm(`定期タスク「${editing.title}」を削除しますか？\n\nこれから先の未完了の回も消えます（完了した回・期限の過ぎた回は残ります）。`)) return;
    try {
      await api.deleteRecurring(editing.id);
      await onSaved();
      await showList();
    } catch (err) {
      errorBox.textContent = err.message;
    }
  });

  document.getElementById("recurring-new").addEventListener("click", () => showForm());
  document.getElementById("recurring-back").addEventListener("click", showList);
  document.getElementById("recurring-close").addEventListener("click", () => dialog.close());

  return {
    async open() {
      await showList();
      dialog.showModal();
    },
    setOptions({ areas, related }) {
      areaNames = areas.map((a) => a.name);
      relatedNames = related.map((r) => r.name);
    },
  };
}
