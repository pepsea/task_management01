import { addDays, dayDiff, formatShort, isWeekend, parseDate, parseDateTime, startOfDay, startOfWeek } from "./dates.js";
import { el } from "./ui.js";

// minDayWidth は画面が狭いときの下限。広いときは空き幅いっぱいまで広げる
const SCALES = {
  week: { days: 14, minDayWidth: 28 },
  month: { minDayWidth: 18 },
};
// style.css の .g-cells の列幅の合計＋右罫線
const CELLS_WIDTH = 520;
const PRIORITY_LABEL = { high: "高", mid: "中", low: "低" };
const COLUMNS = ["領域", "関連項目", "タスク名", "開始", "期限", "優先", "完了"];

function computeRange(scale, anchor) {
  if (scale === "week") {
    return { start: startOfWeek(anchor), days: SCALES.week.days, minDayWidth: SCALES.week.minDayWidth };
  }
  const start = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
  const days = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0).getDate();
  return { start, days, minDayWidth: SCALES.month.minDayWidth };
}

function sortTasks(tasks) {
  return [...tasks].sort(
    (a, b) => a.area.localeCompare(b.area, "ja") || a.start_at.localeCompare(b.start_at) || a.id - b.id,
  );
}

export function createGantt(root, { onEdit, onToggleDone, onEditDecision }) {
  let scale = "week";
  let anchor = startOfDay(new Date());
  let tasks = [];
  let decisions = [];
  // 表示期間内にあるディシジョンの列番号（render のたびに計算し直す）
  let decisionDays = [];

  const decisionLine = (index, range) =>
    el("div", { class: "g-decision-line", style: `left:${index * range.dayWidth + range.dayWidth / 2}px` });

  function decisionRow(range) {
    const byDay = new Map();
    for (const d of decisions) {
      const index = dayDiff(range.start, parseDate(d.date));
      if (index < 0 || index >= range.days) continue;
      if (!byDay.has(index)) byDay.set(index, []);
      byDay.get(index).push(d);
    }
    const track = el("div", {
      class: "g-track g-decision-track",
      style: `width:${range.days * range.dayWidth}px`,
    });
    for (const [index, items] of byDay) {
      track.append(decisionLine(index, range));
      track.append(el("div", {
        class: "g-decision",
        style: `left:${index * range.dayWidth + range.dayWidth / 2}px`,
      }, items.map((d) => el("button", {
        type: "button",
        title: `${d.date}${d.time ? ` ${d.time}` : ""}\n${d.title}`,
        onclick: () => onEditDecision(d),
      }, `◆ ${d.title}`))));
    }
    return el("div", { class: "g-row g-decisions" },
      el("div", { class: "g-cells" }, el("div", { class: "g-decision-caption" }, "ディシジョン")),
      track);
  }

  function headerRow(range) {
    const today = startOfDay(new Date());
    const days = [];
    for (let i = 0; i < range.days; i++) {
      const d = addDays(range.start, i);
      const showMonth = i === 0 || d.getDate() === 1;
      days.push(el("div", {
        class: `g-day${isWeekend(d) ? " weekend" : ""}${dayDiff(today, d) === 0 ? " is-today" : ""}`,
      }, showMonth ? `${d.getMonth() + 1}/` : "", el("br"), String(d.getDate())));
    }
    return el("div", { class: "g-row g-head" },
      el("div", { class: "g-cells" }, COLUMNS.map((c) => el("div", {}, c))),
      el("div", { class: "g-track" }, days));
  }

  function taskRow(task, range, now) {
    const start = parseDateTime(task.start_at);
    const due = parseDateTime(task.due_at);
    const overdue = !task.done && due < now;
    const checkbox = el("input", {
      type: "checkbox",
      checked: task.done,
      "aria-label": "完了",
      onclick: (e) => e.stopPropagation(),
      onchange: (e) => onToggleDone(task, e.target.checked),
    });

    const track = el("div", { class: "g-track", style: `width:${range.days * range.dayWidth}px` });
    const first = Math.max(dayDiff(range.start, start), 0);
    const last = Math.min(dayDiff(range.start, due), range.days - 1);
    if (last >= 0 && first <= range.days - 1 && first <= last) {
      track.append(el("div", {
        class: `g-bar ${task.priority}`,
        title: `${task.title}\n${formatShort(task.start_at)} 〜 ${formatShort(task.due_at)}`,
        style: `left:${first * range.dayWidth + 2}px;width:${(last - first + 1) * range.dayWidth - 4}px`,
      }));
    }
    const todayIndex = dayDiff(range.start, now);
    if (todayIndex >= 0 && todayIndex < range.days) {
      track.append(el("div", {
        class: "g-today",
        style: `left:${todayIndex * range.dayWidth + range.dayWidth / 2}px`,
      }));
    }
    for (const index of decisionDays) {
      track.append(decisionLine(index, range));
    }

    return el("div", {
      class: `g-row${task.done ? " done" : ""}${overdue ? " overdue" : ""}`,
      onclick: () => onEdit(task),
    },
      el("div", { class: "g-cells" },
        el("div", { title: task.area }, task.area),
        el("div", { title: task.related }, task.related),
        el("div", { class: "g-title", title: task.title }, task.title),
        el("div", {}, formatShort(task.start_at)),
        el("div", { class: "g-due" }, formatShort(task.due_at)),
        el("div", { class: `prio ${task.priority}` }, PRIORITY_LABEL[task.priority]),
        el("div", {}, checkbox)),
      track);
  }

  function render(nextTasks = tasks, nextDecisions = decisions) {
    tasks = nextTasks;
    decisions = nextDecisions;
    const range = computeRange(scale, anchor);
    const available = root.clientWidth - CELLS_WIDTH;
    range.dayWidth = Math.max(range.minDayWidth, Math.floor(available / range.days));
    root.style.setProperty("--day-w", `${range.dayWidth}px`);
    decisionDays = [...new Set(
      decisions
        .map((d) => dayDiff(range.start, parseDate(d.date)))
        .filter((index) => index >= 0 && index < range.days),
    )];
    const now = new Date();
    const rows = sortTasks(tasks).map((t) => taskRow(t, range, now));
    root.replaceChildren(
      headerRow(range),
      decisionRow(range),
      ...(rows.length ? rows : [el("div", { class: "g-empty" }, "タスクがありません。「＋ タスク」から追加できます。")]),
    );
  }

  function rangeLabel() {
    const range = computeRange(scale, anchor);
    const end = addDays(range.start, range.days - 1);
    const f = (d) => `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`;
    return `${f(range.start)} 〜 ${f(end)}`;
  }

  let resizeTimer = null;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => render(), 100);
  });

  return {
    render,
    rangeLabel,
    setScale(next) {
      scale = next;
      render();
    },
    shift(direction) {
      anchor = scale === "week"
        ? addDays(anchor, 7 * direction)
        : new Date(anchor.getFullYear(), anchor.getMonth() + direction, 1);
      render();
    },
    goToday() {
      anchor = startOfDay(new Date());
      render();
    },
  };
}
