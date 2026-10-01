export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "style") node.style.cssText = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : String(child));
  }
  return node;
}

export function toast(message) {
  const area = document.getElementById("toast-area");
  const node = el("div", { class: "toast" }, message);
  area.append(node);
  setTimeout(() => node.remove(), 4000);
}

export function tagChip(tag, { onRemove } = {}) {
  return el("span", { class: "tag", style: `background:${tag.color}`, title: tag.name },
    tag.name,
    onRemove
      ? el("button", { type: "button", "aria-label": `タグ「${tag.name}」を外す`, onclick: onRemove }, "×")
      : null);
}

// リンク先の種類（サーバーの app/models.py の link_kind と同じ判定）。
//   web: http(s)://  smb: smb://  path: C:\…  \\サーバー\…  //サーバー/…  file://…  それ以外は null
export function linkKind(value) {
  if (/^https?:\/\/[^\s/]+/i.test(value)) return "web";
  if (/^smb:\/\/[^\s/]+/i.test(value)) return "smb";
  if (/^([A-Za-z]:[\\/]|\\\\[^\\]|\/\/[^/]|file:\/\/\/?\S)/i.test(value)) return "path";
  return null;
}

// パスを、エクスプローラーや Finder のアドレス欄に貼り付けられる形にする。
//   file:///C:/a%20b → C:\a b、file://server/share → \\server\share、file:///Users/x → /Users/x
//   前後の " は外す（Windows の「パスのコピー」で付く）
export function pathForCopy(target) {
  let path = target.trim().replace(/^"(.*)"$/, "$1");
  const file = path.match(/^file:\/\/(.*)$/i);
  if (file) {
    let rest = file[1];
    try {
      rest = decodeURIComponent(rest);
    } catch {
      // %の並びが壊れているときはそのまま
    }
    if (/^\/[A-Za-z]:/.test(rest)) path = rest.slice(1).replaceAll("/", "\\");
    else if (rest.startsWith("/")) path = rest;
    else path = `\\\\${rest.replaceAll("/", "\\")}`;
  }
  return path;
}

// パスをコピーして知らせる（ブラウザからはパスを直接開けないため）
export async function copyPath(target) {
  const path = pathForCopy(target);
  if (await copyText(path)) toast(`パスをコピーしました。エクスプローラーや Finder のアドレス欄に貼り付けて開いてください\n${path}`);
  else toast(`コピーできませんでした: ${path}`);
}

// 文字列をクリップボードにコピーする。成功したら true。
// navigator.clipboard は https か localhost でしか使えないので（社内サーバーを http で開いた場合など）、
// 使えないときは選択してコピーする昔からの方法に切り替える
export async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // 下の方法を試す
    }
  }
  const area = document.createElement("textarea");
  area.value = text;
  area.setAttribute("readonly", "");
  area.style.cssText = "position:fixed;top:0;left:0;opacity:0;pointer-events:none";
  document.body.append(area);
  area.select();
  let ok = false;
  try {
    ok = document.execCommand("copy");
  } catch {
    ok = false;
  }
  area.remove();
  return ok;
}

// 画面の表示倍率（％）。Windows の表示スケール（125%・150% など）で文字が大きく見えるときに下げる。
// ブラウザごとに保存するので、Mac と Windows で別の倍率にできる
export const ZOOM_CHOICES = [70, 80, 90, 100, 110, 120];
const ZOOM_STORAGE_KEY = "ui.zoom";

export function savedZoom() {
  try {
    const value = Number(localStorage.getItem(ZOOM_STORAGE_KEY));
    return ZOOM_CHOICES.includes(value) ? value : 100;
  } catch {
    return 100;
  }
}

export function applyZoom(percent = savedZoom()) {
  document.documentElement.style.zoom = percent === 100 ? "" : String(percent / 100);
}

export function saveZoom(percent) {
  try {
    localStorage.setItem(ZOOM_STORAGE_KEY, String(percent));
  } catch {
    // 保存できない環境ではその場だけ
  }
  applyZoom(percent);
}

// マウスの移動量（画面上の px）をページ内の px に直すための倍率
export const pageZoom = () => Number(document.documentElement.style.zoom) || 1;
