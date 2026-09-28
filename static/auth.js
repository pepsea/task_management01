// ログイン画面・初回設定画面（ログインしていなくても開ける画面なので、他の JS は読み込まない）
const page = document.body.dataset.page;
const form = document.getElementById("auth-form");
const errorBox = document.getElementById("auth-error");
const field = (name) => form.elements.namedItem(name);

async function post(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (res.ok) return;
  let message = `エラーが発生しました (${res.status})`;
  try {
    const data = await res.json();
    if (typeof data.detail === "string") message = data.detail;
    else if (res.status === 422) {
      message = page === "setup" ? "ユーザー名を入力し、パスワードは 8 文字以上にしてください" : "入力内容を確認してください";
    }
  } catch {
    // JSON でない応答は既定のメッセージのまま
  }
  throw new Error(message);
}

// すでにログイン済み・設定済みなら、正しい画面へ移る
fetch("/api/auth/status")
  .then((res) => res.json())
  .then((status) => {
    if (status.logged_in) location.replace("/");
    else if (page === "login" && status.needs_setup) location.replace("/setup.html");
    else if (page === "setup" && !status.needs_setup) location.replace("/login.html");
  })
  .catch(() => {});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorBox.textContent = "";
  const username = field("username").value.trim();
  const password = field("password").value;
  if (page === "setup" && password !== field("confirm").value) {
    errorBox.textContent = "パスワード（確認）が一致しません";
    return;
  }
  try {
    await post(page === "setup" ? "/api/auth/setup" : "/api/auth/login", { username, password });
    location.replace("/");
  } catch (err) {
    errorBox.textContent = err.message;
    field("password").select();
  }
});

field("username").focus();
