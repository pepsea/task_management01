const DAY_MS = 24 * 60 * 60 * 1000;
const pad = (n) => String(n).padStart(2, "0");

// "YYYY-MM-DDTHH:MM" はタイムゾーンなしなのでローカル時刻として解釈される
export function parseDateTime(s) {
  return new Date(s);
}

export function startOfDay(d) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

export function addDays(d, n) {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
}

export function startOfWeek(d) {
  const day = startOfDay(d);
  const offset = (day.getDay() + 6) % 7; // 月曜 = 0
  return addDays(day, -offset);
}

export function dayDiff(a, b) {
  return Math.round((startOfDay(b) - startOfDay(a)) / DAY_MS);
}

export function toInputValue(d) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// "YYYY-MM-DDTHH:MM" → "M/D"
export function formatMonthDay(s) {
  const d = parseDateTime(s);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

// サーバーの ISO 日時（秒・マイクロ秒付き）を「2026/9/28 21:14」形式にする。今年なら年を省く
export function formatStamp(iso) {
  const d = new Date(iso);
  const year = d.getFullYear() === new Date().getFullYear() ? "" : `${d.getFullYear()}/`;
  return `${year}${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// "YYYY-MM-DD" → 今年なら "M/D"、それ以外は "YYYY/M/D"
export function formatDateLabel(s) {
  const d = parseDate(s);
  const year = d.getFullYear() === new Date().getFullYear() ? "" : `${d.getFullYear()}/`;
  return `${year}${d.getMonth() + 1}/${d.getDate()}`;
}

export function isWeekend(d) {
  return d.getDay() === 0 || d.getDay() === 6;
}

// 今日の日付 "YYYY-MM-DD"（ローカル時刻）
export function todayKey() {
  return toInputValue(new Date()).slice(0, 10);
}

export function parseDate(s) {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, m - 1, d);
}
