import { addDays, dayDiff, formatMonthDay, formatStamp, isWeekend, parseDate, parseDateTime, startOfDay, startOfWeek, toInputValue, todayKey } from "./dates.js";
import { copyPath, el, linkKind, pageZoom } from "./ui.js";

// 1 列の単位ごとの設定。表示する列数は空き幅に minColWidth の列が何本入るかで決め、
// minCount〜maxCount に収める（入りきらないときは横スクロール）。
// nominalDays は列幅の下限を 1 日あたりに換算するための日数
const SCALES = {
  // Windows の表示拡大（125%・150%）などで画面が狭く扱われても日数が減りすぎないよう、
  // 列幅の下限は小さめにして、日表示は最低 14 日を並べる
  day: { minCount: 14, maxCount: 21, minColWidth: 18, nominalDays: 1 },
  week: { minCount: 8, maxCount: 13, minColWidth: 36, nominalDays: 7 },
  month: { minCount: 6, maxCount: 12, minColWidth: 44, nominalDays: 30 },
};
// 左の表の列。width は初期幅（px）。detail の列は「登録・開始・期限・優先・完了」としてまとめて折りたためる。
// 見出しの右端をドラッグすると幅を変えられ、幅と折りたたみの状態はブラウザ（localStorage）に保存する
const TABLE_COLUMNS = [
  { key: "today", label: "☀", width: 32, resizable: false },
  { key: "area", label: "領域", width: 90 },
  { key: "related", label: "関連項目", width: 100 },
  { key: "title", label: "タスク名", width: 240 },
  { key: "created", label: "登録", width: 60, detail: true },
  { key: "start", label: "開始", width: 60, detail: true },
  { key: "due", label: "期限", width: 60, detail: true },
  { key: "prio", label: "優先", width: 42, detail: true },
  { key: "done", label: "完了", width: 42, detail: true },
];
const MIN_COLUMN_WIDTH = 32;
const TABLE_STORAGE_KEY = "gantt.table";

function loadTableSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem(TABLE_STORAGE_KEY) ?? "{}");
    return { widths: saved.widths ?? {}, collapsed: Boolean(saved.collapsed), sort: saved.sort ?? null };
  } catch {
    return { widths: {}, collapsed: false, sort: null };
  }
}

function saveTableSettings(settings) {
  try {
    localStorage.setItem(TABLE_STORAGE_KEY, JSON.stringify(settings));
  } catch {
    // 保存できない環境（プライベートモードなど）では、その場だけの設定にする
  }
}
// ディシジョン名 1 件ぶんのおおよその表示幅（重なり判定用）と 1 段の高さ
const DECISION_LABEL_WIDTH = 122;
const DECISION_LANE_HEIGHT = 20;
// ディシジョンの行は最大 2 段（重ならなければ 1 段）
const DECISION_MAX_LANES = 2;
const DUE_SOON_DAYS = 2;
const PRIORITY_LABEL = { high: "高", mid: "中", low: "低" };

// 表示期間を列の配列にする。各列は { start: Date, days: その列が占める日数 }
function buildColumns(scale, anchor, count) {
  const columns = [];
  if (scale === "day" || scale === "week") {
    const step = scale === "day" ? 1 : 7;
    // 日表示は anchor の日から（スライドで 1 日ずつ動かせる）、週表示はその週の月曜から
    const start = scale === "day" ? startOfDay(anchor) : startOfWeek(anchor);
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

// リンクの表示名。登録した表示名、なければ Web は「ドメイン/…」、パスは最後のフォルダ・ファイル名
function linkText(link) {
  if (link.label) return link.label;
  if (linkKind(link.url) === "web") {
    const url = new URL(link.url);
    return url.pathname.length > 1 || url.search ? `${url.host}/…` : url.host;
  }
  return link.url.split(/[\\/]/).filter(Boolean).pop() ?? link.url;
}

// リンクがあればタスク名の下に並べる（行の編集は開かない）。
// Web は新しいタブで、smb:// はそのまま開く。パスはブラウザから開けないので、クリックでコピーする
function linkList(links) {
  const usable = (links ?? []).filter((link) => linkKind(link.url));
  if (!usable.length) return null;
  return el("div", { class: "g-links" }, usable.map((link) => {
    const kind = linkKind(link.url);
    const title = link.label ? `${link.label}\n${link.url}` : link.url;
    if (kind === "path") {
      return el("a", {
        href: "#",
        class: "path-link",
        title: `${title}\n（クリックでパスをコピー）`,
        onclick: (e) => {
          e.preventDefault();
          e.stopPropagation();
          copyPath(link.url);
        },
      }, `📁 ${linkText(link)}`);
    }
    return el("a", {
      href: link.url,
      ...(kind === "web" ? { target: "_blank", rel: "noopener noreferrer" } : {}),
      title,
      onclick: (e) => e.stopPropagation(),
    }, `${kind === "smb" ? "🗂" : "🔗"} ${linkText(link)}`);
  }));
}

// 土曜は "sat"、日曜は "sun"、平日は ""
function weekendOf(date) {
  if (!isWeekend(date)) return "";
  return date.getDay() === 6 ? "sat" : "sun";
}

// 並び順のまとまり: 今日のタスク → 実施中（開始日が今日以前） → まだ始まっていない → 完了（今日のタスクでも一番下）
const PRIORITY_ORDER = { high: 0, mid: 1, low: 2 };

function sortRank(task, today) {
  if (task.done) return 3;
  if (task.today_on === today) return 0;
  return task.start_at.slice(0, 10) <= today ? 1 : 2;
}

// 見出しをクリックしたときの並べ替え（昇順の比べ方。降順はこの逆）。空の関連項目は昇順で最後に回す
const textOrder = (a, b) => (a === "") - (b === "") || a.localeCompare(b, "ja");
const COLUMN_SORTS = {
  today: (a, b, today) => (b.today_on === today) - (a.today_on === today),
  area: (a, b) => textOrder(a.area, b.area),
  related: (a, b) => textOrder(a.related, b.related),
  title: (a, b) => textOrder(a.title, b.title),
  // 登録日は表示は日付だけだが、並べ替えは時刻まで見る
  created: (a, b) => a.created_at.localeCompare(b.created_at),
  start: (a, b) => a.start_at.slice(0, 10).localeCompare(b.start_at.slice(0, 10)),
  due: (a, b) => a.due_at.slice(0, 10).localeCompare(b.due_at.slice(0, 10)),
  prio: (a, b) => PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority],
  done: (a, b) => a.done - b.done,
};

// 標準の並び: 今日のタスク → 実施中 → まだ始まっていない → 完了、その中は期限の近い順 → 優先度の高い順 → 登録の古い順。
// sort（{ key, dir }）があれば、その列の順を先にして、同じものは標準の並びにする。
// どの並べ替えでも、完了したタスクは一番下にまとめる
function sortTasks(tasks, sort) {
  const today = todayKey();
  const byColumn = sort && COLUMN_SORTS[sort.key];
  const direction = sort?.dir === "desc" ? -1 : 1;
  return [...tasks].sort(
    (a, b) => a.done - b.done
      || (byColumn ? direction * byColumn(a, b, today) : 0)
      || sortRank(a, today) - sortRank(b, today)
      || a.due_at.slice(0, 10).localeCompare(b.due_at.slice(0, 10))
      || PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority]
      || a.created_at.localeCompare(b.created_at)
      || a.id - b.id,
  );
}

export function createGantt(root, { onEdit, onToggleDone, onToggleToday, onEditDecision, onChangeDates }) {
  let scale = "day";
  let anchor = startOfWeek(new Date());
  let tasks = [];
  let decisions = [];
  // 領域名 → 色（登録画面で自動割り当て・変更）
  let areaColors = {};
  const table = loadTableSettings();

  const visibleColumns = () => TABLE_COLUMNS.filter((c) => !(c.detail && table.collapsed));
  const widthOf = (column) => table.widths[column.key] ?? column.width;
  // 左の表の幅（列幅の合計＋右罫線）
  const cellsWidth = () => visibleColumns().reduce((sum, c) => sum + widthOf(c), 0) + 1;

  function startResize(e, column) {
    e.preventDefault();
    const startX = e.clientX;
    const startWidth = widthOf(column);
    let frame = null;
    const move = (ev) => {
      table.widths[column.key] = Math.max(MIN_COLUMN_WIDTH, Math.round(startWidth + (ev.clientX - startX) / pageZoom()));
      if (!frame) {
        frame = requestAnimationFrame(() => {
          frame = null;
          render();
        });
      }
    };
    const up = () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
      document.body.classList.remove("col-resizing");
      saveTableSettings(table);
      render();
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
    document.body.classList.add("col-resizing");
  }

  function resetWidth(column) {
    delete table.widths[column.key];
    saveTableSettings(table);
    render();
  }

  function toggleDetails() {
    table.collapsed = !table.collapsed;
    saveTableSettings(table);
    render();
  }

  // 見出しのクリックで並べ替え: 昇順 → 降順 → 標準の並び
  function toggleSort(column) {
    const current = table.sort?.key === column.key ? table.sort.dir : null;
    table.sort = current === null ? { key: column.key, dir: "asc" }
      : current === "asc" ? { key: column.key, dir: "desc" } : null;
    saveTableSettings(table);
    render();
  }

  function headerCell(column) {
    const toggle = column.key === "title"
      ? el("button", {
        type: "button",
        class: "collapse-toggle",
        title: table.collapsed ? "登録・開始・期限・優先・完了を表示する" : "登録・開始・期限・優先・完了を折りたたむ",
        onclick: toggleDetails,
      }, table.collapsed ? "▸ 詳細" : "◂")
      : null;
    const resizer = column.resizable === false
      ? null
      : el("span", {
        class: "col-resizer",
        title: "ドラッグで幅を変更（ダブルクリックで元の幅に戻す）",
        onmousedown: (e) => startResize(e, column),
        ondblclick: () => resetWidth(column),
      });
    const sorted = table.sort?.key === column.key ? table.sort.dir : null;
    const label = el("button", {
      type: "button",
      class: `g-head-label${sorted ? " sorted" : ""}`,
      title: sorted === "asc" ? "クリックで逆順に並べ替え"
        : sorted === "desc" ? "クリックで標準の並び（今日 → 実施中 → 期限 → 優先度 → 登録、完了は下）に戻す"
          : `クリックで「${column.label}」の順に並べ替え`,
      onclick: () => toggleSort(column),
    }, column.label, sorted ? el("span", { class: "sort-mark" }, sorted === "asc" ? "▲" : "▼") : null);
    return el("div", { class: `g-head-cell${toggle ? " has-toggle" : ""}` }, label, toggle, resizer);
  }

  // 表示期間と、日付 → 横位置（px）の換算をまとめたもの。render のたびに作り直す
  function columnCount() {
    const { minCount, maxCount, minColWidth } = SCALES[scale];
    const available = root.clientWidth - cellsWidth();
    return Math.min(maxCount, Math.max(minCount, Math.floor(available / minColWidth)));
  }

  function computeLayout() {
    const columns = buildColumns(scale, anchor, columnCount());
    const start = columns[0].start;
    const totalDays = columns.reduce((sum, c) => sum + c.days, 0);
    const { minColWidth, nominalDays } = SCALES[scale];
    const available = root.clientWidth - cellsWidth();
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

  // 列の区切り線。日表示では土日の列に背景の帯も敷く（ディシジョン行・タスク行の共通の下地）
  function gridLines(layout) {
    const nodes = [];
    let offset = 0;
    for (const column of layout.columns) {
      const left = offset * layout.pxPerDay;
      const weekendClass = scale === "day" ? weekendOf(column.start) : "";
      if (weekendClass) {
        nodes.push(el("div", { class: `g-weekend-band ${weekendClass}`, style: `left:${left}px;width:${layout.pxPerDay}px` }));
      }
      nodes.push(el("div", { class: "g-grid-line", style: `left:${left}px` }));
      offset += column.days;
    }
    return nodes;
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
      const weekendClass = scale === "day" ? weekendOf(column.start) : "";
      return el("div", {
        class: `g-col${weekendClass ? ` weekend ${weekendClass}` : ""}${containsToday ? " is-today" : ""}`,
        style: `width:${column.days * layout.pxPerDay}px`,
      }, top, el("br"), bottom);
    });
    return el("div", { class: "g-row g-head" },
      el("div", { class: "g-cells" }, visibleColumns().map(headerCell)),
      el("div", { class: "g-track", style: `width:${layout.width}px` }, cells));
  }

  function decisionRow(layout) {
    const visible = decisions
      .map((d) => ({ d, index: layout.dayIndex(parseDate(d.date)) }))
      .filter(({ index }) => layout.inRange(index))
      .sort((a, b) => a.index - b.index || (a.d.time ?? "").localeCompare(b.d.time ?? ""));
    // 1 件ずつ、名前が重ならない上の段に置く。重なるものは 2 段目へ（行の高さも 2 段になる）。
    // 2 段とも埋まっているときは、空くのが早い方の段に重ねて置く（◆ にマウスを乗せると名前が見える）
    const laneEnds = [];
    const placed = visible.map(({ d, index }) => {
      const left = centerOf(index, layout);
      let lane = laneEnds.findIndex((end) => left - 7 >= end);
      if (lane === -1) {
        lane = laneEnds.length < DECISION_MAX_LANES ? laneEnds.length : laneEnds.indexOf(Math.min(...laneEnds));
      }
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


  // バーのドラッグで開始日・期限を 1 日単位で変える（時刻はそのまま）。
  //   edge = "start": 左端で開始日 / "end": 右端で期限 / "move": バー全体で両方をずらす（期間の長さは同じ）
  // ドラッグ直後に行のクリック（編集ダイアログ）が発生しないよう、少しの間クリックを無視する
  let ignoreClickUntil = 0;

  function startBarDrag(e, task, edge, layout, bar) {
    if (e.button !== 0) return;
    e.preventDefault();
    e.stopPropagation();
    const start = parseDateTime(task.start_at);
    const due = parseDateTime(task.due_at);
    const original = edge === "start" ? start : due;
    const startX = e.clientX;
    const origLeft = parseFloat(bar.style.left);
    const origWidth = parseFloat(bar.style.width);
    // 期限が開始より前にならない範囲（日数）を求める
    const spanDays = dayDiff(parseDateTime(task.start_at), parseDateTime(task.due_at));
    const fits = (d) => (edge === "start"
      ? toInputValue(addDays(original, d)) <= task.due_at
      : toInputValue(addDays(original, d)) >= task.start_at);
    const limit = edge === "start" ? (fits(spanDays) ? spanDays : spanDays - 1) : (fits(-spanDays) ? -spanDays : -spanDays + 1);
    const label = (d) => {
      if (edge === "move") {
        return `${formatMonthDay(toInputValue(addDays(start, d)))} 〜 ${formatMonthDay(toInputValue(addDays(due, d)))}`;
      }
      return `${edge === "start" ? "開始" : "期限"} ${formatMonthDay(toInputValue(addDays(original, d)))}`;
    };
    const tip = el("span", { class: "g-bar-tip" });
    bar.append(tip);
    bar.classList.add("resizing");
    document.body.classList.add("bar-resizing");
    if (edge === "move") document.body.classList.add("bar-moving");
    let days = 0;

    const move = (ev) => {
      let d = Math.round((ev.clientX - startX) / pageZoom() / layout.pxPerDay);
      if (edge === "start") d = Math.min(d, limit);
      if (edge === "end") d = Math.max(d, limit);
      days = d;
      const px = d * layout.pxPerDay;
      if (edge === "start") {
        bar.style.left = `${origLeft + px}px`;
        bar.style.width = `${origWidth - px}px`;
      } else if (edge === "end") {
        bar.style.width = `${origWidth + px}px`;
      } else {
        bar.style.left = `${origLeft + px}px`;
      }
      tip.textContent = label(d);
    };
    const up = () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
      document.body.classList.remove("bar-resizing", "bar-moving");
      if (days === 0) {
        // 動かさなかった（ただのクリック）なら、そのまま行のクリック（編集ダイアログ）に任せる
        tip.remove();
        bar.classList.remove("resizing");
        return;
      }
      ignoreClickUntil = Date.now() + 300;
      const patch = {};
      if (edge !== "end") patch.start_at = toInputValue(addDays(start, days));
      if (edge !== "start") patch.due_at = toInputValue(addDays(due, days));
      onChangeDates(task, patch);
    };
    tip.textContent = label(0);
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
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
    const startIndex = layout.dayIndex(parseDateTime(task.start_at));
    const dueIndex = layout.dayIndex(due);
    const first = Math.max(startIndex, 0);
    const last = Math.min(dueIndex, layout.totalDays - 1);
    if (first <= last) {
      const left = first * layout.pxPerDay;
      const width = Math.max((last - first + 1) * layout.pxPerDay, 4);
      const barLabel = task.related ? `${task.area} / ${task.related}` : task.area;
      const bar = el("div", {
        class: "g-bar",
        title: `${task.title}\n${barLabel}\n${formatMonthDay(task.start_at)} 〜 ${formatMonthDay(task.due_at)}\n（ドラッグで移動、両端のドラッグで開始・期限を変更）`,
        // バーの色は領域の色（登録画面で設定）。優先度は「優先」の列の文字色で表す
        style: `left:${left + 1}px;width:${width - 2}px;background:${areaColors[task.area] ?? "#9ca3af"}`,
      },
      // バーの中に領域と関連項目を書く（短いバーでは末尾を「…」で省く）
      el("span", { class: "g-bar-label" }, barLabel));
      // 表示期間の外まで続いている側の端は見えていないので、つかめないようにする
      if (startIndex >= 0) {
        bar.append(el("span", {
          class: "g-bar-handle start",
          title: "ドラッグで開始日を変更",
          onmousedown: (e) => startBarDrag(e, task, "start", layout, bar),
          onclick: (e) => e.stopPropagation(),
        }));
      }
      if (dueIndex <= layout.totalDays - 1) {
        bar.append(el("span", {
          class: "g-bar-handle end",
          title: "ドラッグで期限を変更",
          onmousedown: (e) => startBarDrag(e, task, "end", layout, bar),
          onclick: (e) => e.stopPropagation(),
        }));
      }
      bar.addEventListener("mousedown", (e) => startBarDrag(e, task, "move", layout, bar));
      track.append(bar);
    }

    return el("div", {
      class: `g-row${task.done ? " done" : ""}${overdue ? " overdue" : ""}${dueSoon ? " due-soon" : ""}${isToday ? " today-task" : ""}`,
      onclick: () => {
        if (Date.now() < ignoreClickUntil) return;
        onEdit(task);
      },
    },
      el("div", { class: "g-cells" }, visibleColumns().map((column) => {
        switch (column.key) {
          case "today": return el("div", { class: "g-today-cell" }, todayButton);
          case "area": return el("div", { title: task.area },
            el("span", { class: "area-chip", style: `background:${areaColors[task.area] ?? "#9ca3af"}` }, task.area));
          case "related": return el("div", { title: task.related }, task.related);
          case "title": {
            const links = linkList(task.links);
            return el("div", { class: `g-title-cell${links ? " has-links" : ""}` },
              el("div", { class: "g-title", title: task.memo ? `${task.title}\n\n${task.memo}` : task.title },
                // 定期タスクから作った回には 🔁 を付ける
                task.recurring_id ? el("span", { class: "recurring-mark", title: "定期タスク" }, "🔁") : null,
                task.title),
              links);
          }
          // 開始・期限は月日だけを表示する
          case "created": return el("div", { title: `登録 ${formatStamp(task.created_at)}` }, formatMonthDay(task.created_at));
          case "start": return el("div", {}, formatMonthDay(task.start_at));
          // 期限が迫っている・過ぎたときは、日付を赤い背景の目印にする（style.css の .due-mark）
          case "due": return el("div", { class: "g-due" },
            el("span", { class: "due-mark" }, formatMonthDay(task.due_at)));
          case "prio": return el("div", { class: `prio ${task.priority}` }, PRIORITY_LABEL[task.priority]);
          default: return el("div", {}, checkbox);
        }
      })),
      track);
  }

  function render(nextTasks = tasks, nextDecisions = decisions) {
    tasks = nextTasks;
    decisions = nextDecisions;
    root.style.setProperty("--cells-template", visibleColumns().map((c) => `${widthOf(c)}px`).join(" "));
    // 折りたたみ中は期限の列が見えないので、期限が近い・過ぎたタスク名を赤くする（style.css）
    root.classList.toggle("details-collapsed", table.collapsed);
    const layout = computeLayout();
    // 列が細いときは日付見出しの文字を小さくする（style.css の .narrow-cols）
    root.classList.toggle("narrow-cols", layout.pxPerDay * SCALES[scale].nominalDays < 30);
    const now = new Date();
    const rows = sortTasks(tasks, table.sort).map((t) => taskRow(t, layout, now));
    root.replaceChildren(
      headerRow(layout),
      decisionRow(layout),
      ...(rows.length ? rows : [el("div", { class: "g-empty" }, "タスクがありません。「＋ タスク」から追加できます。")]),
    );
  }

  // 表示期間を units 単位（日表示は 1 日、週表示は 1 週、月表示は 1 か月）ずらす
  function panBy(units) {
    if (!units) return;
    if (scale === "day") anchor = addDays(anchor, units);
    else if (scale === "week") anchor = addDays(anchor, 7 * units);
    else anchor = new Date(anchor.getFullYear(), anchor.getMonth() + units, 1);
    render();
  }

  // 1 単位ぶんの横幅（px）
  const unitWidth = () => computeLayout().pxPerDay * (scale === "day" ? 1 : scale === "week" ? 7 : 30);

  // スライド中の表示。offset（px、右へ動かすと正）だけ中身をずらして見せる。
  // 1 単位を超えたぶんは期間を描き直し、残り（半単位以内）を CSS の --pan で指に追従させる
  const pan = { units: 0, frame: null, offset: 0 };
  function setPanOffset(offset) {
    pan.offset = offset;
    if (pan.frame) return;
    pan.frame = requestAnimationFrame(() => {
      pan.frame = null;
      const width = unitWidth();
      const units = -Math.round(pan.offset / width);
      panBy(units - pan.units);
      pan.units = units;
      root.style.setProperty("--pan", `${pan.offset + units * width}px`);
    });
  }
  function endPan() {
    cancelAnimationFrame(pan.frame);
    pan.frame = null;
    // 最後の位置で描き直してから、ずれ（半単位以内）を戻す
    const units = -Math.round(pan.offset / unitWidth());
    panBy(units - pan.units);
    pan.units = 0;
    pan.offset = 0;
    root.style.removeProperty("--pan");
    root.classList.remove("panning");
  }

  // 日付の部分（見出し・ディシジョン行・タスク行の右側）の空いた所をドラッグすると、期間を左右にスライドする。
  // バー・ボタン・入力欄の上では始めない
  root.addEventListener("mousedown", (e) => {
    if (e.button !== 0 || !e.target.closest(".g-track") || e.target.closest(".g-bar, button, input, a, .g-decision")) return;
    e.preventDefault();
    const startX = e.clientX;
    root.classList.add("panning");
    const move = (ev) => setPanOffset((ev.clientX - startX) / pageZoom());
    const up = (ev) => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
      document.body.classList.remove("gantt-panning");
      endPan();
      // ドラッグした後のクリックで編集画面が開かないようにする
      if (Math.abs(ev.clientX - startX) > 3) ignoreClickUntil = Date.now() + 300;
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
    document.body.classList.add("gantt-panning");
  });

  // トラックパッドの左右スワイプ（横スクロール）でもスライドする。止まったら区切りに合わせる
  let wheelTimer = null;
  root.addEventListener("wheel", (e) => {
    if (Math.abs(e.deltaX) <= Math.abs(e.deltaY) || !e.target.closest(".g-track")) return;
    e.preventDefault();
    root.classList.add("panning");
    setPanOffset(pan.offset - e.deltaX / pageZoom());
    clearTimeout(wheelTimer);
    wheelTimer = setTimeout(endPan, 150);
  }, { passive: false });

  let resizeTimer = null;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function redraw() {
      // バーのドラッグ中に描き直すとドラッグが消えるので、終わるまで待つ
      if (document.body.classList.contains("bar-resizing")) {
        resizeTimer = setTimeout(redraw, 200);
        return;
      }
      render();
    }, 100);
  });

  return {
    render,
    setAreaColors(colors) {
      areaColors = colors;
    },
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
      anchor = startOfWeek(new Date());
      render();
    },
  };
}
