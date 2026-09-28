import { api } from "./api.js";
import { el, tagChip, toast } from "./ui.js";

// app/routers/tags.py の TAG_COLORS と同じ並び
const TAG_COLORS = ["#2563eb", "#16a34a", "#dc2626", "#d97706", "#7c3aed", "#db2777", "#0891b2", "#4b5563"];

const areaList = document.getElementById("area-list");
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

function areaCard(area) {
  const addRelated = el("form", { class: "add-row small" },
    el("input", { name: "name", placeholder: "関連項目を追加（例：PJ-A）", "aria-label": `${area.name} に関連項目を追加`, required: true }),
    el("button", { type: "submit" }, "追加"));
  addRelated.addEventListener("submit", (e) => {
    e.preventDefault();
    const name = addRelated.elements.namedItem("name").value.trim();
    if (name) run(() => api.createRelated(area.id, name));
  });

  return el("div", { class: "area-card" },
    el("div", { class: "area-head" },
      nameInput(area.name, "領域名", (name) => api.renameArea(area.id, name)),
      el("button", {
        type: "button",
        class: "danger",
        onclick: () => confirm(`領域「${area.name}」と、その関連項目を削除しますか？`) && run(() => api.deleteArea(area.id)),
      }, "削除")),
    el("ul", { class: "related-list" },
      area.related.length
        ? area.related.map((r) => el("li", {},
          nameInput(r.name, "関連項目名", (name) => api.renameRelated(r.id, name)),
          el("button", {
            type: "button",
            class: "danger",
            "aria-label": `関連項目「${r.name}」を削除`,
            onclick: () => confirm(`関連項目「${r.name}」を削除しますか？`) && run(() => api.deleteRelated(r.id)),
          }, "×")))
        : el("li", { class: "empty" }, "関連項目はまだありません")),
    addRelated);
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
    const [areas, tags] = await Promise.all([api.listAreas(), api.listTags()]);
    areaList.replaceChildren(...(areas.length
      ? areas.map(areaCard)
      : [el("p", { class: "empty" }, "領域はまだありません。上の欄から追加してください。")]));
    tagList.replaceChildren(...(tags.length
      ? tags.map(tagRow)
      : [el("li", { class: "empty" }, "タグはまだありません")]));
  } catch (err) {
    toast(err.message);
  }
}

const areaForm = document.getElementById("area-add");
areaForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const input = areaForm.elements.namedItem("name");
  const name = input.value.trim();
  if (!name) return;
  run(async () => {
    await api.createArea(name);
    input.value = "";
  });
});

load();
