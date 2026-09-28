import { api } from "./api.js";
import { createSortable } from "./sortable.js";
import { el, toast } from "./ui.js";

// TODO 画面右上のリンクリスト。
//   web（http/https）: 新しいタブで開く
//   smb（smb://）    : そのまま開く（Mac では Finder が開く。ブラウザが確認を出すことがある）
//   path（C:\… \\サーバー\… file://）: ブラウザからは開けないので、クリックでパスをコピーする
const ICONS = { web: "🌐", smb: "🗂", path: "📁" };

const list = document.getElementById("link-list");
const form = document.getElementById("link-form");
const errorBox = document.getElementById("link-form-error");
const field = (name) => form.elements.namedItem(name);

let links = [];
let editingId = null;

const sortable = createSortable({
  list,
  getItems: () => links,
  setItems: (items) => {
    links = items;
    render();
  },
  groupOf: () => "all",
  onReorder: async (ids) => {
    try {
      await api.reorderLinks(ids);
    } catch (err) {
      toast(err.message);
    }
    await load();
  },
});

// サーバーで判定した種類に加えて、href に入れる前に書き出しの形も確かめる（javascript: などを防ぐ）
function openableHref(link) {
  if (link.kind === "web" && /^https?:\/\//i.test(link.target)) return link.target;
  if (link.kind === "smb" && /^smb:\/\//i.test(link.target)) return link.target;
  return null;
}

async function copyPath(link) {
  try {
    await navigator.clipboard.writeText(link.target);
    toast("パスをコピーしました。エクスプローラーや Finder のアドレス欄に貼り付けて開いてください");
  } catch {
    toast(`コピーできませんでした: ${link.target}`);
  }
}

function linkLabel(link) {
  const text = link.title || link.target;
  const href = openableHref(link);
  const attrs = { class: "link-label", title: link.target };
  if (href) {
    return el("a", { ...attrs, href, ...(link.kind === "web" ? { target: "_blank", rel: "noopener noreferrer" } : {}) }, text);
  }
  return el("button", { ...attrs, type: "button", title: `${link.target}\n（クリックでパスをコピー）`, onclick: () => copyPath(link) }, text);
}

function render() {
  if (!links.length) {
    list.replaceChildren(el("li", { class: "empty" }, "よく使うリンクを「＋」から登録できます"));
    return;
  }
  list.replaceChildren(...links.map((link) =>
    el("li", { ...sortable(link) },
      el("span", { class: "drag-handle", title: "ドラッグで並べ替え", "aria-hidden": "true" }, "⋮⋮"),
      el("span", { class: "link-icon", "aria-hidden": "true" }, ICONS[link.kind]),
      linkLabel(link),
      el("button", { type: "button", class: "link-action", title: "編集", "aria-label": "編集", onclick: () => openForm(link) }, "✎"),
      el("button", {
        type: "button",
        class: "link-action danger",
        title: "削除",
        "aria-label": "削除",
        onclick: () => remove(link),
      }, "×"))));
}

async function load() {
  try {
    links = await api.listLinks();
    render();
  } catch (err) {
    toast(err.message);
  }
}

function openForm(link = null) {
  editingId = link ? link.id : null;
  field("title").value = link ? link.title : "";
  field("target").value = link ? link.target : "";
  errorBox.textContent = "";
  form.hidden = false;
  field(link ? "title" : "target").focus();
}

function closeForm() {
  form.hidden = true;
  editingId = null;
}

async function remove(link) {
  if (!confirm(`「${link.title || link.target}」を削除しますか？`)) return;
  try {
    await api.deleteLink(link.id);
    await load();
  } catch (err) {
    toast(err.message);
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = { title: field("title").value.trim(), target: field("target").value.trim() };
  if (!payload.target) {
    errorBox.textContent = "リンク先を入力してください";
    return;
  }
  try {
    if (editingId === null) await api.createLink(payload);
    else await api.updateLink(editingId, payload);
    closeForm();
    await load();
  } catch (err) {
    errorBox.textContent = err.message === "入力内容を確認してください"
      ? "http(s)://、smb://、C:\\…、\\\\サーバー\\…、file:// の形で入力してください"
      : err.message;
  }
});
form.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeForm();
});
document.getElementById("link-add").addEventListener("click", () => (form.hidden ? openForm() : closeForm()));
document.getElementById("link-cancel").addEventListener("click", closeForm);

load();
