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
    const areaNames = areas.map((a) => a.name);
    areaFilter.replaceChildren(
      el("option", { value: "" }, "すべての領域"),
      ...areaNames.map((name) => el("option", { value: name }, name)),
    );
    // 絞り込み中の領域が登録画面で消された場合は「すべて」に戻す
    areaFilter.value = areaNames.includes(selected) ? selected : "";
    if (areaFilter.value !== selected) tasks = await api.listTasks("");
    taskForm.setOptions(areas);
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
  rangeLabel.textContent = gantt.rangeLabel();
}

areaFilter.addEventListener("change", loadTasks);
for (const button of scaleButtons) button.addEventListener("click", () => setScale(button.dataset.scale));
document.getElementById("prev").addEventListener("click", () => { gantt.shift(-1); rangeLabel.textContent = gantt.rangeLabel(); });
document.getElementById("next").addEventListener("click", () => { gantt.shift(1); rangeLabel.textContent = gantt.rangeLabel(); });
document.getElementById("today").addEventListener("click", () => { gantt.goToday(); rangeLabel.textContent = gantt.rangeLabel(); });
document.getElementById("add-task").addEventListener("click", () => taskForm.open());
document.getElementById("add-decision").addEventListener("click", () => decisionForm.open());

loadTasks();
loadDecisions();
