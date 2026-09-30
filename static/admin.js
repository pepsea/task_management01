import { api } from "./api.js";
import { formatStamp } from "./dates.js";
import { el, saveZoom, savedZoom, toast, ZOOM_CHOICES } from "./ui.js";

// 管理画面: 表示・バックアップ・データのエクスポート（リンクのみ）・パスワード変更

// 画面の大きさ（このブラウザに保存）
const zoomSelect = document.getElementById("zoom-select");
zoomSelect.replaceChildren(...ZOOM_CHOICES.map((z) => el("option", { value: z }, `${z}%`)));
zoomSelect.value = String(savedZoom());
zoomSelect.addEventListener("change", () => saveZoom(Number(zoomSelect.value)));

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
// バックアップの日付を 8 桁で（例：20260929）
const dateDigits = (date) =>
  `${date.getFullYear()}${String(date.getMonth() + 1).padStart(2, "0")}${String(date.getDate()).padStart(2, "0")}`;

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
              await loadBackups();
            } catch (err) {
              toast(err.message);
            }
          },
        }, "復元"),
        el("button", {
          type: "button",
          class: "danger",
          onclick: async () => {
            // うっかり消さないよう、そのバックアップの日付を入力してもらう
            const created = new Date(b.created_at);
            const dateLabel = dateDigits(created);
            const answer = prompt(
              `${formatStamp(b.created_at)} のバックアップを削除します。削除すると元に戻せません。\n\n削除する場合は、このバックアップの日付「${dateLabel}」を 8 桁の数字で入力してください。`,
            );
            if (answer === null) return;
            if (answer.normalize("NFKC").trim() !== dateLabel) {
              toast(`入力が日付「${dateLabel}」と一致しないため、削除しませんでした`);
              return;
            }
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
