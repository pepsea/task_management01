import { el } from "./ui.js";

// 全ページ共通の上部タブ
const TABS = [
  { href: "./", label: "TODO", paths: ["/", "/index.html"] },
  { href: "notes.html", label: "NOTES", paths: ["/notes.html"] },
  { href: "ideas.html", label: "アイディア", paths: ["/ideas.html"] },
  { href: "settings.html", label: "登録", paths: ["/settings.html"] },
  { href: "archive.html", label: "アーカイブ", paths: ["/archive.html"] },
];

const nav = document.getElementById("app-tabs");
nav.replaceChildren(...TABS.map((tab) => {
  const active = tab.paths.includes(location.pathname);
  return el("a", { href: tab.href, class: `app-tab${active ? " active" : ""}`, "aria-current": active ? "page" : null }, tab.label);
}));
