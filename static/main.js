import { api } from "./api.js";
import { initBrainstorm } from "./brainstorm.js";
import { initDecisionForm } from "./decisionForm.js";
import { createGantt } from "./gantt.js";
import { initIdeas } from "./ideas.js";
import { initTaskForm } from "./taskForm.js";
import { el, toast } from "./ui.js";

const areaFilter = document.getElementById("area-filter");
const rangeLabel = document.getElementById("range-label");
let tasks = [];
let decisions = [];

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
  onEditDecision: (decision) => decisionForm.open({ decision }),
});

const taskForm = initTaskForm({
  onSaved: async () => {
    await Promise.all([loadTasks(), ideas.refresh()]);
  },
});

const decisionForm = initDecisionForm({ onSaved: () => loadDecisions() });

const ideas = initIdeas({
  onMakeTask: (idea) => taskForm.open({ defaults: { title: idea.title, idea_id: idea.id } }),
});

initBrainstorm({
  onPromoted: (idea) => ideas.reveal(idea.id),
});

function renderGantt() {
  gantt.render(tasks, decisions);
  rangeLabel.textContent = gantt.rangeLabel();
}

async function loadTasks() {
  try {
    const [areas, loaded] = await Promise.all([api.listAreas(), api.listTasks(areaFilter.value)]);
    tasks = loaded;
    const selected = areaFilter.value;
    areaFilter.replaceChildren(
      el("option", { value: "" }, "すべての領域"),
      ...areas.map((a) => el("option", { value: a }, a)),
    );
    // 絞り込み中の領域がタスク削除で消えた場合は「すべて」に戻す
    areaFilter.value = areas.includes(selected) ? selected : "";
    if (areaFilter.value !== selected) tasks = await api.listTasks("");
    const related = [...new Set(tasks.map((t) => t.related).filter(Boolean))].sort();
    taskForm.setOptions({ areas, related });
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

function setScale(scale) {
  document.getElementById("scale-week").classList.toggle("active", scale === "week");
  document.getElementById("scale-month").classList.toggle("active", scale === "month");
  gantt.setScale(scale);
  rangeLabel.textContent = gantt.rangeLabel();
}

areaFilter.addEventListener("change", loadTasks);
document.getElementById("scale-week").addEventListener("click", () => setScale("week"));
document.getElementById("scale-month").addEventListener("click", () => setScale("month"));
document.getElementById("prev").addEventListener("click", () => { gantt.shift(-1); rangeLabel.textContent = gantt.rangeLabel(); });
document.getElementById("next").addEventListener("click", () => { gantt.shift(1); rangeLabel.textContent = gantt.rangeLabel(); });
document.getElementById("today").addEventListener("click", () => { gantt.goToday(); rangeLabel.textContent = gantt.rangeLabel(); });
document.getElementById("add-task").addEventListener("click", () => taskForm.open());
document.getElementById("add-decision").addEventListener("click", () => decisionForm.open());

loadTasks();
loadDecisions();
