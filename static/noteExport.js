import { copyText, toast } from "./ui.js";

// メモを Markdown の文章にする（エクスポートとコピーで共通）。
// 中身は「# タイトル」の見出しの下に本文（本文が同じ見出しで始まるなら本文のみ）
export function noteMarkdown(note) {
  const title = note.title || "無題";
  const body = note.body.trim();
  // 本文がすでに同じ見出しで始まっていれば、タイトルを重ねない
  const firstLine = body.split("\n", 1)[0].trim();
  return firstLine === `# ${title}` ? `${body}\n` : `# ${title}\n\n${body}\n`;
}

// メモを Markdown ファイル（.md）としてダウンロードする。ファイル名は「日付_タイトル.md」
export function exportNote(note) {
  const title = note.title || "無題";
  // ファイル名に使えない文字は _ に置き換える
  const safeTitle = title.replace(/[\\/:*?"<>|\r\n\t]/g, "_").slice(0, 60);
  const url = URL.createObjectURL(new Blob([noteMarkdown(note)], { type: "text/markdown;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `${note.note_date}_${safeTitle}.md`;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// メモの Markdown をクリップボードにコピーする
export async function copyNote(note) {
  if (await copyText(noteMarkdown(note))) {
    toast(`「${note.title || "無題"}」の Markdown をコピーしました`);
  } else {
    toast("コピーできませんでした");
  }
}
