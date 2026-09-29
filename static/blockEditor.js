import { api } from "./api.js";
import { el } from "./ui.js";

// Markdown を「ブロック」に分ける。空行で区切り、``` のコードブロックは空行を含めて 1 ブロックにする
export function splitBlocks(text) {
  const blocks = [];
  let current = [];
  let inCode = false;
  const flush = () => {
    if (current.length) blocks.push(current.join("\n"));
    current = [];
  };
  for (const line of text.replace(/\r\n/g, "\n").split("\n")) {
    if (line.trimStart().startsWith("```")) {
      current.push(line);
      inCode = !inCode;
      if (!inCode) flush();
    } else if (inCode) {
      current.push(line);
    } else if (line.trim() === "") {
      flush();
    } else {
      current.push(line);
    }
  }
  flush();
  return blocks;
}

const LIST_ITEM = /^(\s*)([-*+]|(\d+)\.)\s+(\[[ xX]\]\s+)?/;
const TASK_MARK = /^(\s*(?:[-*+]|\d+\.)\s+\[)([ xX])(\])/;
const hasOpenFence = (text) => (text.match(/^\s*```/gm) ?? []).length % 2 === 1;

/**
 * Typora 風のメモ編集。普段は各ブロックを整形して表示し、クリックしたブロックだけを
 * Markdown の原文（textarea）にして編集する。フォーカスが外れると整形表示に戻る。
 *   ↑ / ↓（先頭行・最終行で）: 前後のブロックへ移る
 *   Enter を 2 回（空行）: 次のブロックを書き始める（コードブロックの中を除く）
 *   Enter（リストの行で）: 次の行にリストの記号を続ける。空の項目で Enter ならリストを終える
 *   Tab / Shift+Tab: 行の字下げ（リストの入れ子）
 *   Backspace（空のブロックで）: ブロックを消して前のブロックへ
 *   Esc: 編集を終える
 */
export function createBlockEditor(root, { onInput }) {
  let blocks = []; // { id, text, html } html は未変換なら null
  let nextId = 1;
  let editingId = null;
  let textarea = null;

  const makeBlock = (text) => ({ id: nextId++, text, html: null });
  const indexOf = (id) => blocks.findIndex((b) => b.id === id);

  function value() {
    return blocks
      .map((b) => (b.id === editingId && textarea ? textarea.value : b.text))
      .map((text) => text.replace(/\s+$/, ""))
      .filter((text) => text.trim() !== "")
      .join("\n\n");
  }

  function changed() {
    onInput(value());
  }

  // 未変換のブロックをサーバーで HTML にして、表示中のノードを差し替える
  async function renderPending() {
    const pending = blocks.filter((b) => b.html === null && b.id !== editingId);
    if (!pending.length) return;
    const texts = pending.map((b) => b.text);
    let result;
    try {
      result = await api.renderMarkdown(texts);
    } catch {
      return;
    }
    pending.forEach((block, i) => {
      if (block.text !== texts[i]) return; // 変換中に書き換えられた
      block.html = result.html[i];
      const node = root.querySelector(`.md-block[data-id="${block.id}"]`);
      if (node) fillBlock(node, block);
    });
  }

  function fillBlock(node, block) {
    if (block.html === null) {
      // 変換が終わるまでは原文をそのまま出しておく
      node.textContent = block.text;
      node.classList.add("pending");
      return;
    }
    node.classList.remove("pending");
    node.innerHTML = block.html; // サーバー側（nh3）で無害化済みの HTML
    for (const a of node.querySelectorAll("a")) a.target = "_blank";
    for (const box of node.querySelectorAll('input[type="checkbox"]')) box.disabled = false;
  }

  function blockNode(block) {
    const node = el("div", { class: "md-block", "data-id": block.id });
    fillBlock(node, block);
    node.addEventListener("click", (e) => {
      if (e.target.closest("a")) return; // リンクは開くだけ
      const box = e.target.closest('input[type="checkbox"]');
      if (box) {
        e.preventDefault();
        toggleTask(block, [...node.querySelectorAll('input[type="checkbox"]')].indexOf(box));
        return;
      }
      startEdit(block.id, "end");
    });
    return node;
  }

  function tailNode() {
    const empty = blocks.length === 0;
    return el("div", {
      class: `md-tail${empty ? " empty" : ""}`,
      onclick: () => appendAndEdit(),
    }, empty ? "クリックして書き始める（Markdown が使えます）" : "");
  }

  function draw() {
    const nodes = blocks.map((block) => {
      if (block.id !== editingId) return blockNode(block);
      if (!textarea) textarea = createTextarea(block.text);
      return textarea;
    });
    root.replaceChildren(...nodes, tailNode());
    if (textarea) autosize();
  }

  function createTextarea(text) {
    const ta = el("textarea", { class: "md-edit", rows: "1", spellcheck: "false", "aria-label": "Markdown を編集" });
    ta.value = text;
    ta.addEventListener("input", onTextInput);
    ta.addEventListener("keydown", onKeyDown);
    ta.addEventListener("blur", () => {
      // 別のブロックをクリックした場合はそちらの処理（startEdit）に任せる
      setTimeout(() => {
        if (textarea === ta && document.activeElement !== ta) {
          commit();
          draw();
        }
      }, 150);
    });
    return ta;
  }

  function autosize() {
    textarea.style.height = "auto";
    textarea.style.height = `${textarea.scrollHeight + 2}px`;
  }

  function focusTextarea(caret) {
    if (!textarea) return;
    textarea.focus();
    const pos = caret === "start" ? 0 : textarea.value.length;
    textarea.setSelectionRange(pos, pos);
  }

  // 編集中のブロックを確定する。空行で分かれていれば複数ブロックに、空なら削除。
  // 戻り値: 確定したブロックの位置と、置き換わったブロック数
  function commit() {
    if (editingId === null || !textarea) return { index: -1, count: 0 };
    const index = indexOf(editingId);
    const pieces = splitBlocks(textarea.value).map(makeBlock);
    blocks.splice(index, 1, ...pieces);
    editingId = null;
    textarea = null;
    renderPending();
    return { index, count: pieces.length };
  }

  function startEdit(id, caret) {
    if (editingId === id) return;
    commit();
    if (indexOf(id) === -1) return;
    editingId = id;
    draw();
    focusTextarea(caret);
  }

  function insertAndEdit(index, text = "") {
    const block = makeBlock(text);
    blocks.splice(index, 0, block);
    editingId = block.id;
    draw();
    focusTextarea("end");
  }

  function appendAndEdit() {
    commit();
    const last = blocks[blocks.length - 1];
    if (last && !last.text.trim()) startEdit(last.id, "end");
    else insertAndEdit(blocks.length);
  }

  function toggleTask(block, nth) {
    let count = -1;
    block.text = block.text
      .split("\n")
      .map((line) => {
        if (!TASK_MARK.test(line)) return line;
        count += 1;
        return count === nth ? line.replace(TASK_MARK, (_, a, mark, b) => `${a}${mark === " " ? "x" : " "}${b}`) : line;
      })
      .join("\n");
    block.html = null;
    draw();
    renderPending();
    changed();
  }

  function onTextInput() {
    autosize();
    const { value: text, selectionStart } = textarea;
    // 最後で Enter を 2 回押したら（空行）、次のブロックへ進む
    if (selectionStart === text.length && /\n\n$/.test(text) && !hasOpenFence(text)) {
      textarea.value = text.replace(/\n+$/, "");
      const { index, count } = commit();
      insertAndEdit(index + count);
    }
    changed();
  }

  function currentLine() {
    const { value: text, selectionStart } = textarea;
    const start = text.lastIndexOf("\n", selectionStart - 1) + 1;
    const end = text.indexOf("\n", selectionStart);
    return { start, end: end === -1 ? text.length : end };
  }

  function replaceRange(start, end, insert, caret) {
    textarea.setRangeText(insert, start, end, "end");
    if (caret !== undefined) textarea.setSelectionRange(caret, caret);
    onTextInput();
  }

  function onKeyDown(e) {
    if (e.isComposing || e.keyCode === 229) return; // 日本語の変換中は何もしない
    const { value: text, selectionStart, selectionEnd } = textarea;
    const collapsed = selectionStart === selectionEnd;

    if (e.key === "Escape") {
      e.preventDefault();
      commit();
      draw();
      return;
    }
    if (e.key === "ArrowUp" && collapsed && !text.slice(0, selectionStart).includes("\n")) {
      const index = indexOf(editingId);
      if (index > 0) {
        e.preventDefault();
        startEdit(blocks[index - 1].id, "end");
      }
      return;
    }
    if (e.key === "ArrowDown" && collapsed && !text.slice(selectionEnd).includes("\n")) {
      e.preventDefault();
      const { index, count } = commit();
      const next = blocks[index + count];
      if (next) startEdit(next.id, "start");
      else if (count > 0) insertAndEdit(index + count);
      else draw();
      return;
    }
    if (e.key === "Backspace" && collapsed && selectionStart === 0 && text === "") {
      const index = indexOf(editingId);
      e.preventDefault();
      blocks.splice(index, 1);
      editingId = null;
      textarea = null;
      const prev = blocks[index - 1];
      if (prev) startEdit(prev.id, "end");
      else draw();
      changed();
      return;
    }
    if (e.key === "Tab") {
      e.preventDefault();
      const { start } = currentLine();
      if (e.shiftKey) {
        const remove = text.slice(start, start + 2).match(/^ {1,2}/)?.[0].length ?? 0;
        if (remove) replaceRange(start, start + remove, "", Math.max(start, selectionStart - remove));
      } else {
        replaceRange(start, start, "  ", selectionStart + 2);
      }
      return;
    }
    if (e.key === "Enter" && !e.shiftKey && collapsed && !hasOpenFence(text.slice(0, selectionStart))) {
      const { start, end } = currentLine();
      const line = text.slice(start, end);
      const m = line.match(LIST_ITEM);
      if (!m || selectionStart < start + m[0].length) return;
      e.preventDefault();
      if (line.trim() === m[0].trim()) {
        // 中身のない項目で Enter: 記号を消してリストを終える
        replaceRange(start, end, "", start);
        return;
      }
      const [, indent, , number, task] = m;
      const marker = number ? `${Number(number) + 1}.` : m[2];
      replaceRange(selectionStart, selectionStart, `\n${indent}${marker} ${task ? "[ ] " : ""}`);
    }
  }

  return {
    // 編集中のブロックで選んでいる文字を before / after で囲む。囲めたら true
    // （編集中でない・文字を選んでいないときは false）
    wrapSelection(before, after) {
      if (!textarea) return false;
      const { selectionStart: start, selectionEnd: end, value: text } = textarea;
      if (start === end) return false;
      textarea.setRangeText(`${before}${text.slice(start, end)}${after}`, start, end, "select");
      textarea.focus();
      onTextInput();
      return true;
    },
    // 表示するメモを入れ替える（編集中の内容は破棄）
    setValue(text) {
      editingId = null;
      textarea = null;
      blocks = splitBlocks(text).map(makeBlock);
      draw();
      renderPending();
    },
    value,
    // 新しいメモなど、すぐに書き始めたいとき
    startWriting() {
      appendAndEdit();
    },
  };
}
