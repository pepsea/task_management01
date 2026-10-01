import { api } from "./api.js";
import { initBrainstorm } from "./brainstorm.js";
import { initDecisionForm } from "./decisionForm.js";
import { initRecurringForm } from "./recurringForm.js";
import { createGantt } from "./gantt.js";
import { initTaskForm } from "./taskForm.js";
import { todayKey } from "./dates.js";
import { toast } from "./ui.js";

const taskSearch = document.getElementById("task-search");
const todayFilter = document.getElementById("today-filter");
let tasks = [];
let decisions = [];
let todayOnly = false;

const gantt = createGantt(document.getElementById("gantt"), {
  onEdit: (task) => taskForm.open({ task }),
  onToggleDone: async (task, done) => {
    try {
      await api.updateTask(task.id, { done });
    } catch (err) {
      toast(err.message);
    }
    await loadTasks();
  },
  onToggleToday: async (task, on) => {
    try {
      await api.updateTask(task.id, { today_on: on ? todayKey() : null });
    } catch (err) {
      toast(err.message);
    }
    await loadTasks();
  },
  onChangeDates: async (task, patch) => {
    try {
      await api.updateTask(task.id, patch);
    } catch (err) {
      toast(err.message);
    }
    await loadTasks();
  },
  onEditDecision: (decision) => decisionForm.open({ decision }),
});

const taskForm = initTaskForm({
  onSaved: async () => {
    await loadTasks();
  },
});

const decisionForm = initDecisionForm({ onSaved: () => loadDecisions() });
const recurringForm = initRecurringForm({ onSaved: () => loadTasks() });

initBrainstorm({
  onPromoted: (idea) => toast(`「${idea.title}」をアイディア保管庫に移しました`),
});

// アイディア保管庫の「タスク化」から ?idea=ID 付きで開かれたら、そのアイディアからタスクを作る
async function openTaskFromIdea() {
  const ideaId = new URLSearchParams(location.search).get("idea");
  if (!ideaId) return;
  history.replaceState(null, "", location.pathname);
  try {
    const idea = await api.getIdea(Number(ideaId));
    taskForm.open({ defaults: { title: idea.title, idea_id: idea.id } });
  } catch (err) {
    toast(err.message);
  }
}

// 検索欄の文字（空白区切りはすべてを含むもの）で絞り込む。対象はタスク名・領域・関連項目・メモ・リンク
function matchesSearch(task) {
  const words = taskSearch.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) return true;
  const text = [task.title, task.area, task.related, task.memo, ...task.links.flatMap((l) => [l.label, l.url])]
    .join("\n").toLowerCase();
  return words.every((w) => text.includes(w));
}

function renderGantt() {
  const today = todayKey();
  const todayTasks = tasks.filter((t) => t.today_on === today);
  document.getElementById("today-count").textContent = String(todayTasks.length);
  todayFilter.classList.toggle("on", todayOnly);
  todayFilter.setAttribute("aria-pressed", String(todayOnly));
  gantt.render((todayOnly ? todayTasks : tasks).filter(matchesSearch), decisions);
}

async function loadTasks() {
  try {
    const [areas, related, loaded] = await Promise.all([
      api.listAreas(), api.listRelated(), api.listTasks(),
    ]);
    tasks = loaded;
    taskForm.setOptions({ areas, related });
    recurringForm.setOptions({ areas, related });
    gantt.setAreaColors(Object.fromEntries(areas.map((a) => [a.name, a.color])));
    renderGantt();
  } catch (err) {
    toast(err.message);
  }
}

async function loadDecisions() {
  try {
    decisions = await api.listDecisions();
    renderGantt();
  } catch (err) {
    toast(err.message);
  }
}

const scaleButtons = document.querySelectorAll("[data-scale]");

function setScale(scale) {
  for (const button of scaleButtons) button.classList.toggle("active", button.dataset.scale === scale);
  gantt.setScale(scale);
}

// 右側（リンク・ブレスト）の開け閉め。たたむとガントが横幅いっぱいに広がる。状態はブラウザに覚えておく
const SIDE_STORAGE_KEY = "todo.sideCollapsed";
const appLayout = document.querySelector(".app");
const sideToggle = document.getElementById("side-toggle");

function setSideCollapsed(collapsed) {
  appLayout.classList.toggle("side-collapsed", collapsed);
  sideToggle.textContent = collapsed ? "◂ リンク・ブレスト" : "リンク・ブレスト ▸";
  sideToggle.setAttribute("aria-expanded", String(!collapsed));
  try {
    localStorage.setItem(SIDE_STORAGE_KEY, collapsed ? "1" : "0");
  } catch {
    // 保存できない環境ではその場だけ
  }
  // ガントの幅が変わるので、表示する日数を計算し直す
  renderGantt();
}

let sideCollapsed = false;
try {
  sideCollapsed = localStorage.getItem(SIDE_STORAGE_KEY) === "1";
} catch {
  // 保存できない環境では開いた状態
}
setSideCollapsed(sideCollapsed);
sideToggle.addEventListener("click", () => setSideCollapsed(!appLayout.classList.contains("side-collapsed")));

taskSearch.addEventListener("input", renderGantt);
todayFilter.addEventListener("click", () => {
  todayOnly = !todayOnly;
  renderGantt();
});
for (const button of scaleButtons) button.addEventListener("click", () => setScale(button.dataset.scale));
document.getElementById("prev").addEventListener("click", () => gantt.shift(-1));
document.getElementById("next").addEventListener("click", () => gantt.shift(1));
document.getElementById("today").addEventListener("click", () => gantt.goToday());
document.getElementById("add-task").addEventListener("click", () => taskForm.open());
document.getElementById("add-recurring").addEventListener("click", () => recurringForm.open());
document.getElementById("add-decision").addEventListener("click", () => decisionForm.open());

loadTasks().then(openTaskFromIdea);
loadDecisions();
