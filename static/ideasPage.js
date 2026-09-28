import { initIdeas } from "./ideas.js";

// タスク化はガント画面のタスク作成ダイアログで行う（main.js が ?idea= を受け取って開く）
initIdeas({
  onMakeTask: (idea) => {
    location.href = `./?idea=${encodeURIComponent(idea.id)}`;
  },
});
