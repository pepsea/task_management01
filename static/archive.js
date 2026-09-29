import { api } from "./api.js";
import { formatDateLabel, formatStamp } from "./dates.js";
import { copyNote, exportNote } from "./noteExport.js";
import { el, tagChip, toast } from "./ui.js";

const SEARCH_MS = 300;

const list = document.getElementById("archive-list");
const count = document.getElementById("archive-count");
const search = document.getElementById("archive-search");
const tagFilter = document.getElementById("archive-tag-filter");
const kindButtons = document.querySelectorAll("[data-kind]");
let searchTimer = null;
// 表示中の種類（?kind=notes でメモ、それ以外はアイディア）
let kind = new URLSearchParams(location.search).get("kind") === "notes" ? "notes" : "ideas";

async function run(action) {
  try {
    await action();
    await load();
  } catch (err) {
    toast(err.message);
  }
}

function restoreButton(label, restore, message) {
  return el("button", {
    type: "button",
    class: "primary",
    onclick: (e) => {
      e.stopPropagation();
      run(async () => {
        await restore();
        toast(message);
      });
    },
  }, label);
}

function deleteButton(title, remove) {
  return el("button", {
    type: "button",
    class: "danger",
    onclick: (e) => {
      e.stopPropagation();
      if (confirm(`「${title}」を完全に削除しますか？`)) run(remove);
    },
  }, "削除");
}

// 1 行表示の行。行をクリックすると下に本文と日付を開く
function archiveRow({ title, tags, badge, archivedAt, body, dates, buttons }) {
  const detail = el("div", { class: "archive-detail", hidden: true }, body, el("div", { class: "archive-dates" }, dates));
  const row = el("li", { class: "archive-row" },
    el("div", {
      class: "archive-line",
      title: "クリックで本文を表示",
      onclick: () => {
        detail.hidden = !detail.hidden;
        row.classList.toggle("open", !detail.hidden);
      },
    },
      el("span", { class: "archive-caret", "aria-hidden": "true" }, "▸"),
      el("span", { class: `archive-title${title ? "" : " untitled"}` }, title || "無題"),
      tags.length ? el("span", { class: "tag-chips" }, tags.map((t) => tagChip(t))) : null,
      badge,
      el("span", { class: "spacer" }),
      el("span", { class: "archive-date", title: "アーカイブした日時" }, formatStamp(archivedAt)),
      ...buttons),
    detail);
  return row;
}

function ideaRow(idea) {
  return archiveRow({
    title: idea.title,
    tags: idea.tags,
    badge: idea.task_count > 0 ? el("span", { class: "badge", title: "タスク化済み" }, "✓") : null,
    archivedAt: idea.archived_at,
    body: idea.body.trim()
      ? el("div", { class: "archive-body" }, idea.body)
      : el("div", { class: "archive-body empty" }, "（本文なし）"),
    dates: `思いつき ${formatStamp(idea.created_at)} ・ 更新 ${formatStamp(idea.updated_at)} ・ アーカイブ ${formatStamp(idea.archived_at)}`,
    buttons: [
      restoreButton("戻す", () => api.updateIdea(idea.id, { archived: false }), `「${idea.title}」を保管庫に戻しました`),
      deleteButton(idea.title, () => api.deleteIdea(idea.id)),
    ],
  });
}

function noteRow(note, html) {
  const title = note.title || "無題";
  const body = el("div", { class: "archive-body md-view" });
  if (html) {
    body.innerHTML = html; // サーバー側（nh3）で無害化済みの HTML
    for (const a of body.querySelectorAll("a")) a.target = "_blank";
  } else {
    body.classList.add("empty");
    body.textContent = "（本文なし）";
  }
  return archiveRow({
    title: note.title,
    tags: note.tags,
    badge: el("span", { class: "note-list-date", title: "メモの日付" }, `📅 ${formatDateLabel(note.note_date)}`),
    archivedAt: note.archived_at,
    body,
    dates: `作成 ${formatStamp(note.created_at)} ・ 更新 ${formatStamp(note.updated_at)} ・ アーカイブ ${formatStamp(note.archived_at)}`,
    buttons: [
      el("button", {
        type: "button",
        title: "Markdown の文章をクリップボードにコピー",
        onclick: (e) => {
          e.stopPropagation();
          copyNote(note);
        },
      }, "📋"),
      el("button", {
        type: "button",
        title: "Markdown ファイル（.md）として保存",
        onclick: (e) => {
          e.stopPropagation();
          exportNote(note);
        },
      }, "⬇"),
      restoreButton("戻す", () => api.updateNote(note.id, { archived: false }), `「${title}」をメモ帳に戻しました`),
      deleteButton(title, () => api.deleteNote(note.id)),
    ],
  });
}

async function loadTags() {
  const tags = await api.listTags();
  const selected = tagFilter.value;
  tagFilter.replaceChildren(
    el("option", { value: "" }, "すべてのタグ"),
    ...tags.map((t) => el("option", { value: t.name }, t.name)),
  );
  tagFilter.value = tags.some((t) => t.name === selected) ? selected : "";
}

async function load() {
  for (const button of kindButtons) button.classList.toggle("active", button.dataset.kind === kind);
  try {
    await loadTags();
    const q = search.value.trim();
    let rows;
    if (kind === "notes") {
      const notes = await api.listNotes(q, tagFilter.value, true);
      const { html } = notes.length ? await api.renderMarkdown(notes.map((n) => n.body)) : { html: [] };
      rows = notes.map((note, i) => noteRow(note, html[i]));
    } else {
      rows = (await api.listIdeas(q, tagFilter.value, true)).map(ideaRow);
    }
    const label = kind === "notes" ? "メモ" : "アイディア";
    count.textContent = `${rows.length} 件`;
    list.replaceChildren(rows.length
      ? el("ul", { class: "archive-rows" }, rows)
      : el("p", { class: "empty archive-empty" },
        q || tagFilter.value ? `該当する${label}はありません` : `アーカイブした${label}はまだありません`));
  } catch (err) {
    toast(err.message);
  }
}

for (const button of kindButtons) {
  button.addEventListener("click", () => {
    kind = button.dataset.kind;
    history.replaceState(null, "", kind === "notes" ? "?kind=notes" : location.pathname);
    load();
  });
}
search.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(load, SEARCH_MS);
});
tagFilter.addEventListener("change", load);

load();
