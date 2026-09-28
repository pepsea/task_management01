import { api } from "./api.js";
import { el, tagChip, toast } from "./ui.js";

// app/routers/tags.py の TAG_COLORS と同じ並び
const TAG_COLORS = ["#2563eb", "#16a34a", "#dc2626", "#d97706", "#7c3aed", "#db2777", "#0891b2", "#4b5563"];

const areaList = document.getElementById("area-list");
const relatedList = document.getElementById("related-list");
const tagList = document.getElementById("tag-list");

// 名前の入力欄。Enter かフォーカスを外したときに、変わっていれば onRename を呼ぶ
function nameInput(value, label, onRename) {
  const input = el("input", { value, "aria-label": label });
  const commit = async () => {
    const name = input.value.trim();
    if (!name || name === value) {
      input.value = value;
      return;
    }
    try {
      await onRename(name);
      await load();
    } catch (err) {
      toast(err.message);
      input.value = value;
    }
  };
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.isComposing && e.keyCode !== 229) {
      e.preventDefault();
      input.blur();
    }
  });
  input.addEventListener("change", commit);
  return input;
}

async function run(action) {
  try {
    await action();
    await load();
  } catch (err) {
    toast(err.message);
  }
}

// 領域・関連項目の 1 行。名前はその場で変更でき、× で削除する
function masterRow(item, label, rename, remove) {
  return el("li", {},
    nameInput(item.name, `${label}名`, (name) => rename(item.id, name)),
    el("button", {
      type: "button",
      class: "danger",
      "aria-label": `${label}「${item.name}」を削除`,
      onclick: () => confirm(`${label}「${item.name}」を削除しますか？`) && run(() => remove(item.id)),
    }, "削除"));
}

function renderMasters(listEl, items, label, rename, remove) {
  listEl.replaceChildren(...(items.length
    ? items.map((item) => masterRow(item, label, rename, remove))
    : [el("li", { class: "empty" }, `${label}はまだありません。上の欄から追加してください。`)]));
}

function bindAddForm(formId, create) {
  const form = document.getElementById(formId);
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const input = form.elements.namedItem("name");
    const name = input.value.trim();
    if (!name) return;
    run(async () => {
      await create(name);
      input.value = "";
    });
  });
}

function tagRow(tag) {
  const swatches = TAG_COLORS.map((color) => el("button", {
    type: "button",
    class: `swatch${color === tag.color ? " active" : ""}`,
    style: `background:${color}`,
    "aria-label": `色 ${color}`,
    onclick: () => run(() => api.updateTag(tag.id, { color })),
  }));
  return el("li", {},
    tagChip(tag),
    nameInput(tag.name, "タグ名", (name) => api.updateTag(tag.id, { name })),
    el("span", { class: "swatches" }, swatches),
    el("button", {
      type: "button",
      class: "danger",
      onclick: () => confirm(`タグ「${tag.name}」を削除しますか？（アイディアからも外れます）`) && run(() => api.deleteTag(tag.id)),
    }, "削除"));
}

async function load() {
  try {
    const [areas, related, tags] = await Promise.all([api.listAreas(), api.listRelated(), api.listTags()]);
    renderMasters(areaList, areas, "領域", api.renameArea, api.deleteArea);
    renderMasters(relatedList, related, "関連項目", api.renameRelated, api.deleteRelated);
    tagList.replaceChildren(...(tags.length
      ? tags.map(tagRow)
      : [el("li", { class: "empty" }, "タグはまだありません")]));
  } catch (err) {
    toast(err.message);
  }
}

bindAddForm("area-add", api.createArea);
bindAddForm("related-add", api.createRelated);

load();
