import { addDays, dayDiff, formatShort, isWeekend, parseDate, parseDateTime, startOfDay, startOfWeek } from "./dates.js";
import { el } from "./ui.js";

// 1 列の単位ごとの設定。count は表示する列数、minColWidth は画面が狭いときの列幅の下限
// （広いときは空き幅いっぱいまで広げる）。nominalDays は列幅の下限を 1 日あたりに換算するための日数
const SCALES = {
  day: { count: 14, minColWidth: 28, nominalDays: 1 },
  week: { count: 13, minColWidth: 44, nominalDays: 7 },
  month: { count: 12, minColWidth: 56, nominalDays: 30 },
};
// style.css の .g-cells の列幅の合計＋右罫線
const CELLS_WIDTH = 520;
// ディシジョン名 1 件ぶんのおおよその表示幅（重なり判定用）
const DECISION_LABEL_WIDTH = 90;
const PRIORITY_LABEL = { high: "高", mid: "中", low: "低" };
const COLUMNS = ["領域", "関連項目", "タスク名", "開始", "期限", "優先", "完了"];

// 表示期間を列の配列にする。各列は { start: Date, days: その列が占める日数 }
function buildColumns(scale, anchor) {
  const { count } = SCALES[scale];
  const columns = [];
  if (scale === "day" || scale === "week") {
    const step = scale === "day" ? 1 : 7;
    const start = startOfWeek(anchor);
    for (let i = 0; i < count; i++) columns.push({ start: addDays(start, i * step), days: step });
  } else {
    for (let i = 0; i < count; i++) {
      const start = new Date(anchor.getFullYear(), anchor.getMonth() + i, 1);
      const next = new Date(anchor.getFullYear(), anchor.getMonth() + i + 1, 1);
      columns.push({ start, days: dayDiff(start, next) });
    }
  }
  return columns;
}

function columnLabels(scale, column, index, previous) {
  const d = column.start;
  if (scale === "day") {
    return [index === 0 || d.getDate() === 1 ? `${d.getMonth() + 1}/` : "", String(d.getDate())];
  }
  if (scale === "week") {
    const monthChanged = index === 0 || previous.start.getMonth() !== d.getMonth();
    return [monthChanged ? `${d.getMonth() + 1}月` : "", `${d.getDate()}〜`];
  }
  return [index === 0 || d.getMonth() === 0 ? String(d.getFullYear()) : "", `${d.getMonth() + 1}月`];
}

function sortTasks(tasks) {
  return [...tasks].sort(
    (a, b) => a.area.localeCompare(b.area, "ja") || a.start_at.localeCompare(b.start_at) || a.id - b.id,
  );
}

export function createGantt(root, { onEdit, onToggleDone, onEditDecision }) {
  let scale = "day";
  let anchor = startOfDay(new Date());
  let tasks = [];
  let decisions = [];

  // 表示期間と、日付 → 横位置（px）の換算をまとめたもの。render のたびに作り直す
  function computeLayout() {
    const columns = buildColumns(scale, anchor);
    const start = columns[0].start;
    const totalDays = columns.reduce((sum, c) => sum + c.days, 0);
    const { minColWidth, nominalDays } = SCALES[scale];
    const available = root.clientWidth - CELLS_WIDTH;
    const pxPerDay = Math.max(minColWidth / nominalDays, available / totalDays);
    const today = startOfDay(new Date());
    return {
      columns,
      start,
      totalDays,
      pxPerDay,
      width: totalDays * pxPerDay,
      dayIndex: (date) => dayDiff(start, date),
      inRange: (index) => index >= 0 && index < totalDays,
      todayIndex: dayDiff(start, today),
      decisionDays: [...new Set(decisions.map((d) => dayDiff(start, parseDate(d.date))))]
        .filter((i) => i >= 0 && i < totalDays),
    };
  }

  const centerOf = (index, layout) => (index + 0.5) * layout.pxPerDay;

  function gridLines(layout) {
    let offset = 0;
    return layout.columns.map((column) => {
      const line = el("div", { class: "g-grid-line", style: `left:${offset * layout.pxPerDay}px` });
      offset += column.days;
      return line;
    });
  }

  function markers(layout) {
    const nodes = layout.decisionDays.map((index) =>
      el("div", { class: "g-decision-line", style: `left:${centerOf(index, layout)}px` }));
    if (layout.inRange(layout.todayIndex)) {
      nodes.push(el("div", { class: "g-today", style: `left:${centerOf(layout.todayIndex, layout)}px` }));
    }
    return nodes;
  }

  function headerRow(layout) {
    const today = startOfDay(new Date());
    const cells = layout.columns.map((column, i) => {
      const [top, bottom] = columnLabels(scale, column, i, layout.columns[i - 1]);
      const offset = dayDiff(column.start, today);
      const containsToday = offset >= 0 && offset < column.days;
      const weekend = scale === "day" && isWeekend(column.start);
      return el("div", {
        class: `g-col${weekend ? " weekend" : ""}${containsToday ? " is-today" : ""}`,
        style: `width:${column.days * layout.pxPerDay}px`,
      }, top, el("br"), bottom);
    });
    return el("div", { class: "g-row g-head" },
      el("div", { class: "g-cells" }, COLUMNS.map((c) => el("div", {}, c))),
      el("div", { class: "g-track", style: `width:${layout.width}px` }, cells));
  }

  function decisionRow(layout) {
    const byDay = new Map();
    for (const d of decisions) {
      const index = layout.dayIndex(parseDate(d.date));
      if (!layout.inRange(index)) continue;
      if (!byDay.has(index)) byDay.set(index, []);
      byDay.get(index).push(d);
    }
    const track = el("div", { class: "g-track g-decision-track", style: `width:${layout.width}px` },
      gridLines(layout), markers(layout));
    // 名前が隣と重なるときは下の段に回す（2 段を交互に使う）
    const laneEnds = [-Infinity, -Infinity];
    const entries = [...byDay].sort((x, y) => x[0] - y[0]);
    for (const [index, items] of entries) {
      const left = centerOf(index, layout);
      const lane = left - 7 >= laneEnds[0] ? 0 : left - 7 >= laneEnds[1] ? 1 : 0;
      laneEnds[lane] = left - 7 + Math.min(items.length * DECISION_LABEL_WIDTH, 2 * DECISION_LABEL_WIDTH);
      track.append(el("div", {
        class: "g-decision",
        style: `left:${left}px;top:${2 + lane * 15}px`,
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

  function taskRow(task, layout, now) {
    const due = parseDateTime(task.due_at);
    const overdue = !task.done && due < now;
    const checkbox = el("input", {
      type: "checkbox",
      checked: task.done,
      "aria-label": "完了",
      onclick: (e) => e.stopPropagation(),
      onchange: (e) => onToggleDone(task, e.target.checked),
    });

    const track = el("div", { class: "g-track", style: `width:${layout.width}px` },
      gridLines(layout), markers(layout));
    // バーは開始日の頭から期限日の終わりまで。表示期間の外は切り取る
    const first = Math.max(layout.dayIndex(parseDateTime(task.start_at)), 0);
    const last = Math.min(layout.dayIndex(due), layout.totalDays - 1);
    if (first <= last) {
      const left = first * layout.pxPerDay;
      const width = Math.max((last - first + 1) * layout.pxPerDay, 4);
      track.append(el("div", {
        class: `g-bar ${task.priority}`,
        title: `${task.title}\n${formatShort(task.start_at)} 〜 ${formatShort(task.due_at)}`,
        style: `left:${left + 1}px;width:${width - 2}px`,
      }));
    }

    return el("div", {
      class: `g-row${task.done ? " done" : ""}${overdue ? " overdue" : ""}`,
      onclick: () => onEdit(task),
    },
      el("div", { class: "g-cells" },
        el("div", { title: task.area }, task.area),
        el("div", { title: task.related }, task.related),
        el("div", { class: "g-title", title: task.memo ? `${task.title}\n\n${task.memo}` : task.title },
          task.memo ? el("span", { class: "memo-mark", "aria-label": "メモあり" }, "📝") : null,
          task.title),
        el("div", {}, formatShort(task.start_at)),
        el("div", { class: "g-due" }, formatShort(task.due_at)),
        el("div", { class: `prio ${task.priority}` }, PRIORITY_LABEL[task.priority]),
        el("div", {}, checkbox)),
      track);
  }

  function render(nextTasks = tasks, nextDecisions = decisions) {
    tasks = nextTasks;
    decisions = nextDecisions;
    const layout = computeLayout();
    const now = new Date();
    const rows = sortTasks(tasks).map((t) => taskRow(t, layout, now));
    root.replaceChildren(
      headerRow(layout),
      decisionRow(layout),
      ...(rows.length ? rows : [el("div", { class: "g-empty" }, "タスクがありません。「＋ タスク」から追加できます。")]),
    );
  }

  function rangeLabel() {
    const columns = buildColumns(scale, anchor);
    const last = columns[columns.length - 1];
    const end = addDays(last.start, last.days - 1);
    const f = (d) => `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`;
    return `${f(columns[0].start)} 〜 ${f(end)}`;
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
      if (scale === "day") anchor = addDays(anchor, 7 * direction);
      else if (scale === "week") anchor = addDays(anchor, 28 * direction);
      else anchor = new Date(anchor.getFullYear(), anchor.getMonth() + direction, 1);
      render();
    },
    goToday() {
      anchor = startOfDay(new Date());
      render();
    },
  };
}
