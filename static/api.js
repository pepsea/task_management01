async function request(method, path, body) {
  const options = { method, headers: {} };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(path, options);
  } catch {
    throw new Error("サーバーに接続できません");
  }
  if (!res.ok) {
    let message = `エラーが発生しました (${res.status})`;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") message = data.detail;
      else if (Array.isArray(data.detail)) message = "入力内容を確認してください";
    } catch {
      // JSON でない応答は既定のメッセージのまま
    }
    throw new Error(message);
  }
  return res.status === 204 ? null : res.json();
}

const q = (params) => {
  const s = new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString();
  return s ? `?${s}` : "";
};

export const api = {
  listTasks: (area) => request("GET", `/api/tasks${q({ area })}`),
  createTask: (task) => request("POST", "/api/tasks", task),
  updateTask: (id, patch) => request("PATCH", `/api/tasks/${id}`, patch),
  deleteTask: (id) => request("DELETE", `/api/tasks/${id}`),
  listAreas: () => request("GET", "/api/areas"),
  listRelated: () => request("GET", "/api/related"),
  listIdeas: (search, tag, archived = false) =>
    request("GET", `/api/ideas${q({ q: search, tag, archived: archived ? "true" : "" })}`),
  getIdea: (id) => request("GET", `/api/ideas/${id}`),
  createIdea: (idea) => request("POST", "/api/ideas", idea),
  updateIdea: (id, patch) => request("PATCH", `/api/ideas/${id}`, patch),
  deleteIdea: (id) => request("DELETE", `/api/ideas/${id}`),
  listMemos: () => request("GET", "/api/brainstorm"),
  addMemo: (text) => request("POST", "/api/brainstorm", { text }),
  deleteMemo: (id) => request("DELETE", `/api/brainstorm/${id}`),
  promoteMemo: (id) => request("POST", `/api/brainstorm/${id}/promote`),
  listDecisions: () => request("GET", "/api/decisions"),
  createDecision: (decision) => request("POST", "/api/decisions", decision),
  updateDecision: (id, patch) => request("PATCH", `/api/decisions/${id}`, patch),
  deleteDecision: (id) => request("DELETE", `/api/decisions/${id}`),
  listTags: () => request("GET", "/api/tags"),
  updateTag: (id, patch) => request("PATCH", `/api/tags/${id}`, patch),
  deleteTag: (id) => request("DELETE", `/api/tags/${id}`),
  createArea: (name) => request("POST", "/api/areas", { name }),
  renameArea: (id, name) => request("PATCH", `/api/areas/${id}`, { name }),
  updateArea: (id, patch) => request("PATCH", `/api/areas/${id}`, patch),
  deleteArea: (id) => request("DELETE", `/api/areas/${id}`),
  createRelated: (name) => request("POST", "/api/related", { name }),
  renameRelated: (id, name) => request("PATCH", `/api/related/${id}`, { name }),
  deleteRelated: (id) => request("DELETE", `/api/related/${id}`),
};
