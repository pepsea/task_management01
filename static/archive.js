import { api } from "./api.js";
import { formatStamp } from "./dates.js";
import { el, tagChip, toast } from "./ui.js";

const SEARCH_MS = 300;

const list = document.getElementById("archive-list");
const count = document.getElementById("archive-count");
const search = document.getElementById("archive-search");
const tagFilter = document.getElementById("archive-tag-filter");
let searchTimer = null;

async function run(action) {
  try {
    await action();
    await load();
  } catch (err) {
    toast(err.message);
  }
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
      el("button", {
        type: "button",
        class: "primary",
        onclick: () => run(async () => {
          await api.updateIdea(idea.id, { archived: false });
          toast(`「${idea.title}」を保管庫に戻しました`);
        }),
      }, "保管庫に戻す"),
      el("button", {
        type: "button",
        class: "danger",
        onclick: () => confirm(`「${idea.title}」を完全に削除しますか？`) && run(() => api.deleteIdea(idea.id)),
      }, "削除")));
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
  try {
    await loadTags();
    const ideas = await api.listIdeas(search.value.trim(), tagFilter.value, true);
    const filtered = search.value.trim() || tagFilter.value;
    count.textContent = `${ideas.length} 件`;
    list.replaceChildren(...(ideas.length
      ? ideas.map(ideaCard)
      : [el("p", { class: "empty archive-empty" },
        filtered ? "該当するアイディアはありません" : "アーカイブしたアイディアはまだありません。保管庫の「アーカイブ」で移せます。")]));
  } catch (err) {
    toast(err.message);
  }
}

search.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(load, SEARCH_MS);
});
tagFilter.addEventListener("change", load);

load();
