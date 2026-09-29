import { api } from "./api.js";
import { formatStamp } from "./dates.js";
import { el, toast } from "./ui.js";

// 管理画面: バックアップ・データのエクスポート（リンクのみ）・パスワード変更

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
// 入力された日付がバックアップの日付と同じか。「9/29」「09/29」「2026/9/29」「2026-09-29」、全角数字も可
function matchesDate(input, date) {
  const parts = input.normalize("NFKC").trim().split(/[/\-.年月日\s]+/).filter(Boolean).map(Number);
  if (parts.some(Number.isNaN)) return false;
  const [year, month, day] = parts.length === 3 ? parts : parts.length === 2 ? [date.getFullYear(), ...parts] : [];
  return year === date.getFullYear() && month === date.getMonth() + 1 && day === date.getDate();
}

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
            const dateLabel = `${created.getMonth() + 1}/${created.getDate()}`;
            const answer = prompt(
              `${formatStamp(b.created_at)} のバックアップを削除します。削除すると元に戻せません。\n\n削除する場合は、このバックアップの日付「${dateLabel}」を入力してください。`,
            );
            if (answer === null) return;
            if (!matchesDate(answer, created)) {
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
