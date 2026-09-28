// 一覧の行（<li>）をドラッグで並べ替える。groupOf が同じ値の行の間でだけ動かせる
// （★ の付いた行は常に先頭にまとまるので、★ の有無をまたいでは動かせない）
export function createSortable({ list, getItems, setItems, groupOf, onReorder }) {
  let dragId = null;

  function clear() {
    dragId = null;
    for (const node of list.querySelectorAll(".dragging, .drop-before, .drop-after")) {
      node.classList.remove("dragging", "drop-before", "drop-after");
    }
  }

  const canDrop = (dragged, target) => dragged && dragged.id !== target.id && groupOf(dragged) === groupOf(target);

  // 行の el() に渡す属性
  return function attrs(item) {
    return {
      draggable: "true",
      ondragstart: (e) => {
        dragId = item.id;
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", String(item.id));
        e.currentTarget.classList.add("dragging");
      },
      ondragover: (e) => {
        const dragged = getItems().find((i) => i.id === dragId);
        if (!canDrop(dragged, item)) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        const rect = e.currentTarget.getBoundingClientRect();
        const after = e.clientY > rect.top + rect.height / 2;
        e.currentTarget.classList.toggle("drop-after", after);
        e.currentTarget.classList.toggle("drop-before", !after);
      },
      ondragleave: (e) => e.currentTarget.classList.remove("drop-before", "drop-after"),
      ondrop: (e) => {
        e.preventDefault();
        const after = e.currentTarget.classList.contains("drop-after");
        const items = getItems();
        const dragged = items.find((i) => i.id === dragId);
        clear();
        if (!canDrop(dragged, item)) return;
        const reordered = items.filter((i) => i.id !== dragged.id);
        reordered.splice(reordered.indexOf(item) + (after ? 1 : 0), 0, dragged);
        setItems(reordered);
        onReorder(reordered.map((i) => i.id));
      },
      ondragend: clear,
    };
  };
}
