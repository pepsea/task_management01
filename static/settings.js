import { api } from "./api.js";
import { formatStamp } from "./dates.js";
import { el, tagChip, toast } from "./ui.js";

// app/colors.py の PALETTE と同じ並び
const PALETTE = ["#2563eb", "#16a34a", "#dc2626", "#d97706", "#7c3aed", "#db2777", "#0891b2", "#4b5563"];

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
function swatches(current, onPick) {
  return el("span", { class: "swatches" }, PALETTE.map((color) => el("button", {
    type: "button",
    class: `swatch${color === current ? " active" : ""}`,
    style: `background:${color}`,
    "aria-label": `色 ${color}`,
    onclick: () => run(() => onPick(color)),
  })));
}

function masterRow(item, label, rename, remove) {
  return el("li", {},
    item.color ? el("span", { class: "color-dot", style: `background:${item.color}` }) : null,
    nameInput(item.name, `${label}名`, (name) => rename(item.id, name)),
    item.color ? swatches(item.color, (color) => api.updateArea(item.id, { color })) : null,
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
  return el("li", {},
    tagChip(tag),
    nameInput(tag.name, "タグ名", (name) => api.updateTag(tag.id, { name })),
    swatches(tag.color, (color) => api.updateTag(tag.id, { color })),
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

// パスワード変更（変更すると、このブラウザ以外のログインは解除される）
const passwordForm = document.getElementById("password-form");
const passwordError = document.getElementById("password-error");
passwordForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const value = (name) => passwordForm.elements.namedItem(name).value;
  passwordError.textContent = "";
  if (value("new") !== value("confirm")) {
    passwordError.textContent = "新しいパスワード（確認）が一致しません";
    return;
  }
  try {
    await api.changePassword(value("current"), value("new"));
    passwordForm.reset();
    toast("パスワードを変更しました。他のブラウザのログインは解除されました");
  } catch (err) {
    passwordError.textContent = err.message === "入力内容を確認してください"
      ? "新しいパスワードは 8 文字以上にしてください"
      : err.message;
  }
});

// バックアップ（作成・一覧・復元・ダウンロード・削除）
const backupList = document.getElementById("backup-list");
const BACKUP_KIND = { manual: "手動", "before-restore": "復元前の自動保存" };
const sizeLabel = (bytes) => (bytes < 1024 * 1024 ? `${Math.ceil(bytes / 1024)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`);

async function loadBackups() {
  try {
    const items = await api.listBackups();
    backupList.replaceChildren(...(items.length
      ? items.map((b) => el("li", {},
        el("span", { class: "backup-date" }, formatStamp(b.created_at)),
        el("span", { class: `backup-kind ${b.kind}` }, BACKUP_KIND[b.kind] ?? b.kind),
        el("span", { class: "backup-size" }, sizeLabel(b.size)),
        el("span", { class: "spacer" }),
        el("a", {
          class: "button backup-download",
          href: `/api/backups/${encodeURIComponent(b.name)}/download`,
          title: "バックアップのファイルをダウンロード",
        }, "⬇"),
        el("button", {
          type: "button",
          onclick: async () => {
            if (!confirm(`${formatStamp(b.created_at)} のバックアップに戻しますか？\n\nすべてのデータがその時点に戻ります。今の状態は「復元前の自動保存」として残ります。`)) return;
            try {
              await api.restoreBackup(b.name);
              toast("バックアップから復元しました");
              await Promise.all([load(), loadBackups()]);
            } catch (err) {
              toast(err.message);
            }
          },
        }, "復元"),
        el("button", {
          type: "button",
          class: "danger",
          onclick: async () => {
            if (!confirm(`${formatStamp(b.created_at)} のバックアップを削除しますか？`)) return;
            try {
              await api.deleteBackup(b.name);
              await loadBackups();
            } catch (err) {
              toast(err.message);
            }
          },
        }, "削除")))
      : [el("li", { class: "empty" }, "バックアップはまだありません")]));
  } catch (err) {
    toast(err.message);
  }
}

document.getElementById("backup-create").addEventListener("click", async () => {
  try {
    await api.createBackup();
    toast("バックアップを作成しました");
    await loadBackups();
  } catch (err) {
    toast(err.message);
  }
});

loadBackups();
