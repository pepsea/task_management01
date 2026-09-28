import { api } from "./api.js";
import { el, toast } from "./ui.js";

export function initBrainstorm({ onPromoted }) {
  const input = document.getElementById("bs-input");
  const list = document.getElementById("bs-list");

  function render(memos) {
    if (!memos.length) {
      list.replaceChildren(el("li", { class: "empty" }, "思いついたことを上の欄に書き留めましょう"));
      return;
    }
    list.replaceChildren(...memos.map((memo) =>
      el("li", {},
        el("span", { class: "bs-text" }, memo.text),
        el("button", { type: "button", title: "アイディア保管庫へ移す", onclick: () => promote(memo) }, "→保管庫"),
        el("button", { type: "button", title: "削除", "aria-label": "削除", onclick: () => remove(memo) }, "×"))));
  }

  async function refresh() {
    try {
      render(await api.listMemos());
    } catch (err) {
      toast(err.message);
    }
  }

  async function promote(memo) {
    try {
      const idea = await api.promoteMemo(memo.id);
      await refresh();
      await onPromoted(idea);
    } catch (err) {
      toast(err.message);
    }
  }

  async function remove(memo) {
    try {
      await api.deleteMemo(memo.id);
      await refresh();
    } catch (err) {
      toast(err.message);
    }
  }

  input.addEventListener("keydown", async (e) => {
    // 日本語入力の変換確定の Enter では追加しない
    if (e.key !== "Enter" || e.isComposing || e.keyCode === 229) return;
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    try {
      await api.addMemo(text);
      input.value = "";
      await refresh();
    } catch (err) {
      toast(err.message);
    }
    input.focus();
  });

  refresh();
  return { refresh };
}
