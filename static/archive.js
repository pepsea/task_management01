import { api } from "./api.js";
import { formatDateLabel, formatStamp } from "./dates.js";
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
    onclick: () => run(async () => {
      await restore();
      toast(message);
    }),
  }, label);
}

function deleteButton(title, remove) {
  return el("button", {
    type: "button",
    class: "danger",
    onclick: () => confirm(`「${title}」を完全に削除しますか？`) && run(remove),
  }, "削除");
}

function ideaCard(idea) {
  return el("article", { class: "archive-card" },
    el("header", { class: "archive-card-head" },
      el("h2", {}, idea.title),
      idea.task_count > 0 ? el("span", { class: "badge", title: "タスク化済み" }, `✓ タスク ${idea.task_count}件`) : null),
    idea.tags.length ? el("div", { class: "tag-chips" }, idea.tags.map((t) => tagChip(t))) : null,
    idea.body.trim()
      ? el("div", { class: "archive-body" }, idea.body)
      : el("div", { class: "archive-body empty" }, "（本文なし）"),
    el("footer", { class: "archive-card-foot" },
      el("span", { class: "archive-dates" },
        `思いつき ${formatStamp(idea.created_at)} ・ 更新 ${formatStamp(idea.updated_at)} ・ アーカイブ ${formatStamp(idea.archived_at)}`),
      el("span", { class: "spacer" }),
      restoreButton("保管庫に戻す", () => api.updateIdea(idea.id, { archived: false }), `「${idea.title}」を保管庫に戻しました`),
      deleteButton(idea.title, () => api.deleteIdea(idea.id))));
}

function noteCard(note, html) {
  const body = el("div", { class: "archive-body md-view" });
  if (html) {
    body.innerHTML = html; // サーバー側（nh3）で無害化済みの HTML
    for (const a of body.querySelectorAll("a")) a.target = "_blank";
  } else {
    body.classList.add("empty");
    body.textContent = "（本文なし）";
  }
  return el("article", { class: "archive-card" },
    el("header", { class: "archive-card-head" },
      el("h2", {}, note.title || "無題"),
      el("span", { class: "note-list-date" }, `📅 ${formatDateLabel(note.note_date)}`)),
    note.tags.length ? el("div", { class: "tag-chips" }, note.tags.map((t) => tagChip(t))) : null,
    body,
    el("footer", { class: "archive-card-foot" },
      el("span", { class: "archive-dates" },
        `作成 ${formatStamp(note.created_at)} ・ 更新 ${formatStamp(note.updated_at)} ・ アーカイブ ${formatStamp(note.archived_at)}`),
      el("span", { class: "spacer" }),
      restoreButton("メモ帳に戻す", () => api.updateNote(note.id, { archived: false }), `「${note.title || "無題"}」をメモ帳に戻しました`),
      deleteButton(note.title || "無題", () => api.deleteNote(note.id))));
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
    let cards;
    if (kind === "notes") {
      const notes = await api.listNotes(q, tagFilter.value, true);
      const { html } = notes.length ? await api.renderMarkdown(notes.map((n) => n.body)) : { html: [] };
      cards = notes.map((note, i) => noteCard(note, html[i]));
    } else {
      cards = (await api.listIdeas(q, tagFilter.value, true)).map(ideaCard);
    }
    const label = kind === "notes" ? "メモ" : "アイディア";
    count.textContent = `${cards.length} 件`;
    list.replaceChildren(...(cards.length
      ? cards
      : [el("p", { class: "empty archive-empty" },
        q || tagFilter.value ? `該当する${label}はありません` : `アーカイブした${label}はまだありません`)]));
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
