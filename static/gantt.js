import { addDays, dayDiff, formatShort, isWeekend, parseDate, parseDateTime, startOfDay, startOfWeek, todayKey } from "./dates.js";
import { el, isWebUrl } from "./ui.js";

// 1 列の単位ごとの設定。表示する列数は空き幅に minColWidth の列が何本入るかで決め、
// minCount〜maxCount に収める（入りきらないときは横スクロール）。
// nominalDays は列幅の下限を 1 日あたりに換算するための日数
const SCALES = {
  day: { minCount: 7, maxCount: 21, minColWidth: 38, nominalDays: 1 },
  week: { minCount: 4, maxCount: 13, minColWidth: 56, nominalDays: 7 },
  month: { minCount: 3, maxCount: 12, minColWidth: 64, nominalDays: 30 },
};
// style.css の .g-cells の列幅の合計＋右罫線
const CELLS_WIDTH = 671;
// ディシジョン名 1 件ぶんのおおよその表示幅（重なり判定用）と 1 段の高さ
const DECISION_LABEL_WIDTH = 122;
const DECISION_LANE_HEIGHT = 20;
const DUE_SOON_DAYS = 2;
const PRIORITY_LABEL = { high: "高", mid: "中", low: "低" };
const COLUMNS = ["☀", "領域", "関連項目", "タスク名", "開始", "期限", "優先", "完了"];

// 表示期間を列の配列にする。各列は { start: Date, days: その列が占める日数 }
function buildColumns(scale, anchor, count) {
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

// リンクがあればタスク名の前に 🔗。クリックで最初のリンクを新しいタブで開く（全リンクはツールチップと編集ダイアログで）
function linkMark(links) {
  const usable = (links ?? []).filter((link) => isWebUrl(link.url));
  if (!usable.length) return null;
  return el("a", {
    class: "link-mark",
    href: usable[0].url,
    target: "_blank",
    rel: "noopener noreferrer",
    title: usable.map((link) => (link.label ? `${link.label}: ${link.url}` : link.url)).join("\n"),
    onclick: (e) => e.stopPropagation(),
  }, usable.length > 1 ? `🔗${usable.length}` : "🔗");
}

// 今日のタスク → その他の未完了 → 完了（完了は今日のタスクでも一番下）。
// それぞれ締切（期限）の早い順、同じ締切は開始の早い順
function sortRank(task, today) {
  if (task.done) return 2;
  return task.today_on === today ? 0 : 1;
}

function sortTasks(tasks) {
  const today = todayKey();
  return [...tasks].sort(
    (a, b) => sortRank(a, today) - sortRank(b, today)
      || a.due_at.localeCompare(b.due_at)
      || a.start_at.localeCompare(b.start_at)
      || a.id - b.id,
  );
}

export function createGantt(root, { onEdit, onToggleDone, onToggleToday, onEditDecision }) {
  let scale = "day";
  let anchor = startOfDay(new Date());
  let tasks = [];
  let decisions = [];
  // 領域名 → 色（登録画面で自動割り当て・変更）
  let areaColors = {};

  // 表示期間と、日付 → 横位置（px）の換算をまとめたもの。render のたびに作り直す
  function columnCount() {
    const { minCount, maxCount, minColWidth } = SCALES[scale];
    const available = root.clientWidth - CELLS_WIDTH;
    return Math.min(maxCount, Math.max(minCount, Math.floor(available / minColWidth)));
  }

  function computeLayout() {
    const columns = buildColumns(scale, anchor, columnCount());
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
    const visible = decisions
      .map((d) => ({ d, index: layout.dayIndex(parseDate(d.date)) }))
      .filter(({ index }) => layout.inRange(index))
      .sort((a, b) => a.index - b.index || (a.d.time ?? "").localeCompare(b.d.time ?? ""));
    // 1 件ずつ、名前が重ならない一番上の段に置く。同じ日の複数件や近い日付は下の段に縦に並ぶ
    const laneEnds = [];
    const placed = visible.map(({ d, index }) => {
      const left = centerOf(index, layout);
      let lane = laneEnds.findIndex((end) => left - 7 >= end);
      if (lane === -1) lane = laneEnds.push(0) - 1;
      laneEnds[lane] = left - 7 + DECISION_LABEL_WIDTH;
      return { d, left, lane };
    });
    const lanes = Math.max(laneEnds.length, 1);
    const track = el("div", {
      class: "g-track g-decision-track",
      style: `width:${layout.width}px;height:${lanes * DECISION_LANE_HEIGHT + 6}px`,
    }, gridLines(layout), markers(layout));
    for (const { d, left, lane } of placed) {
      track.append(el("button", {
        type: "button",
        class: "g-decision",
        style: `left:${left}px;top:${3 + lane * DECISION_LANE_HEIGHT}px`,
        title: `${d.date}${d.time ? ` ${d.time}` : ""}\n${d.title}`,
        onclick: () => onEditDecision(d),
      }, `◆ ${d.title}`));
    }
    return el("div", { class: "g-row g-decisions" },
      el("div", { class: "g-cells" }, el("div", { class: "g-decision-caption" }, "ディシジョン")),
      track);
  }


  function taskRow(task, layout, now) {
    const due = parseDateTime(task.due_at);
    const overdue = !task.done && due < now;
    // 期限が今日・明日・明後日（残り 2 日以内）の未完了タスクは期限を赤で表示する
    const dueSoon = !task.done && !overdue && dayDiff(now, due) <= DUE_SOON_DAYS;
    const isToday = task.today_on === todayKey();
    const todayButton = el("button", {
      type: "button",
      class: `today-toggle${isToday ? " on" : ""}`,
      title: isToday ? "今日のタスクから外す" : "今日のタスクにする",
      "aria-pressed": isToday ? "true" : "false",
      onclick: (e) => {
        e.stopPropagation();
        onToggleToday(task, !isToday);
      },
    }, "☀");
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
      class: `g-row${task.done ? " done" : ""}${overdue ? " overdue" : ""}${dueSoon ? " due-soon" : ""}${isToday ? " today-task" : ""}`,
      onclick: () => onEdit(task),
    },
      el("div", { class: "g-cells" },
        el("div", { class: "g-today-cell" }, todayButton),
        el("div", { title: task.area },
          el("span", { class: "area-chip", style: `background:${areaColors[task.area] ?? "#9ca3af"}` }, task.area)),
        el("div", { title: task.related }, task.related),
        el("div", { class: "g-title", title: task.memo ? `${task.title}\n\n${task.memo}` : task.title },
          task.memo ? el("span", { class: "memo-mark", "aria-label": "メモあり" }, "📝") : null,
          linkMark(task.links),
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
    const columns = buildColumns(scale, anchor, columnCount());
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
    setAreaColors(colors) {
      areaColors = colors;
    },
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
