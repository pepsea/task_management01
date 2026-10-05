import { api } from "./api.js";
import { applyZoom, el, toast } from "./ui.js";

// SETTING/DATA タブで選んだ表示倍率を反映する
applyZoom();

// 全ページ共通の上部タブ
const TABS = [
  { href: "./", label: "TODO", paths: ["/", "/index.html"] },
  { href: "ideas.html", label: "IDEA", paths: ["/ideas.html"] },
  { href: "notes.html", label: "NOTES", paths: ["/notes.html"] },
  { href: "settings.html", label: "REGISTRATION", paths: ["/settings.html"] },
  { href: "archive.html", label: "ARCHIVE", paths: ["/archive.html"] },
  { href: "admin.html", label: "SETTING/DATA", paths: ["/admin.html"] },
];

const nav = document.getElementById("app-tabs");
const account = el("span", { class: "app-account" });
const version = el("span", { class: "app-version" });
nav.replaceChildren(
  ...TABS.map((tab) => {
    const active = tab.paths.includes(location.pathname);
    return el("a", { href: tab.href, class: `app-tab${active ? " active" : ""}`, "aria-current": active ? "page" : null }, tab.label);
  }),
  el("span", { class: "spacer" }),
  version,
  account,
);

// 右上に小さくバージョン（コミット番号）。Mac と Linux サーバーで同じものが動いているかを見分ける
api.version()
  .then(({ commit, built_at: builtAt }) => {
    if (!commit) return;
    version.textContent = `v ${commit}`;
    version.title = `バージョン ${commit}${builtAt ? `\n作成 ${builtAt}` : ""}`;
  })
  .catch(() => {});

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
