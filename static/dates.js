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

export function formatShort(s) {
  const d = parseDateTime(s);
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function isWeekend(d) {
  return d.getDay() === 0 || d.getDay() === 6;
}

export function parseDate(s) {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, m - 1, d);
}
