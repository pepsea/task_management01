import { api } from "./api.js";
import { el, toast } from "./ui.js";

// 全ページ共通の上部タブ
const TABS = [
  { href: "./", label: "TODO", paths: ["/", "/index.html"] },
  { href: "notes.html", label: "NOTES", paths: ["/notes.html"] },
  { href: "ideas.html", label: "アイディア", paths: ["/ideas.html"] },
  { href: "settings.html", label: "登録", paths: ["/settings.html"] },
  { href: "archive.html", label: "アーカイブ", paths: ["/archive.html"] },
  { href: "admin.html", label: "管理", paths: ["/admin.html"] },
];

const nav = document.getElementById("app-tabs");
const account = el("span", { class: "app-account" });
nav.replaceChildren(
  ...TABS.map((tab) => {
    const active = tab.paths.includes(location.pathname);
    return el("a", { href: tab.href, class: `app-tab${active ? " active" : ""}`, "aria-current": active ? "page" : null }, tab.label);
  }),
  el("span", { class: "spacer" }),
  account,
);

// 右端にログイン中のユーザー名とログアウト
api.me()
  .then(({ username }) => {
    account.replaceChildren(
      el("span", { class: "app-user", title: "ログイン中のユーザー" }, `👤 ${username}`),
      el("button", {
        type: "button",
        class: "app-logout",
        onclick: async () => {
          try {
            await api.logout();
          } catch (err) {
            toast(err.message);
            return;
          }
          location.assign("/login.html");
        },
      }, "ログアウト"),
    );
  })
  .catch(() => {});
