import { copyText, toast } from "./ui.js";

// どのアプリでも同じように読める Markdown にする。このアプリだけの書き方
// （蛍光ペン ==文== と、文字色 <span style="color:…">文</span>）を取り除き、中の文章だけを残す。
// コード（``` のブロックと ` の中）は変えない。app/markdown_portable.py と同じ処理
const INLINE_CODE = /(`+[^`]*?`+)/;
const HIGHLIGHT = /==(?=\S)([\s\S]+?)(?<=\S)==/g;
const COLOR_SPAN = /<span\s+style="\s*color\s*:[^"]*">([\s\S]*?)<\/span>/g;

function stripAppOnly(text) {
  return text
    .split(INLINE_CODE)
    .map((part, i) => (i % 2 ? part : part.replace(HIGHLIGHT, "$1").replace(COLOR_SPAN, "$1")))
    .join("");
}

export function toPortableMarkdown(text) {
  const out = [];
  let chunk = [];
  let inCode = false;
  for (const line of text.split("\n")) {
    if (/^\s*```/.test(line)) {
      if (!inCode && chunk.length) {
        out.push(stripAppOnly(chunk.join("\n")));
        chunk = [];
      }
      inCode = !inCode;
      out.push(line);
    } else if (inCode) {
      out.push(line);
    } else {
      chunk.push(line);
    }
  }
  if (chunk.length) out.push(stripAppOnly(chunk.join("\n")));
  return out.join("\n");
}

// メモを Markdown の文章にする（エクスポートとコピーで共通）。
// 中身は「# タイトル」の見出しの下に本文（本文が同じ見出しで始まるなら本文のみ）
export function noteMarkdown(note) {
  const title = note.title || "無題";
  const body = toPortableMarkdown(note.body).trim();
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
