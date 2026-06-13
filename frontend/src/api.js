// Tiny fetch wrapper. Handles the optional shared app password (HTTP Basic):
// the password is stored in sessionStorage and sent on every request.

const PW_KEY = "sns_app_password";

export function getPassword() {
  return sessionStorage.getItem(PW_KEY) || "";
}
export function setPassword(pw) {
  sessionStorage.setItem(PW_KEY, pw);
}
export function clearPassword() {
  sessionStorage.removeItem(PW_KEY);
}

function authHeader() {
  const pw = getPassword();
  return pw ? { Authorization: "Basic " + btoa(":" + pw) } : {};
}

async function handle(res) {
  if (res.status === 401) {
    clearPassword();
    const err = new Error("Authentication required");
    err.status = 401;
    throw err;
  }
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail = (data && data.detail) || res.statusText;
    const err = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    err.status = res.status;
    throw err;
  }
  return data;
}

const json = (method, body) => ({
  method,
  headers: { "Content-Type": "application/json", ...authHeader() },
  body: body ? JSON.stringify(body) : undefined,
});

export const api = {
  getSettings: () => fetch("/api/settings", { headers: authHeader() }).then(handle),
  updateSettings: (p) => fetch("/api/settings", json("PUT", p)).then(handle),

  importFile: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch("/api/import", { method: "POST", headers: authHeader(), body: fd }).then(handle);
  },

  listNotes: (status) =>
    fetch("/api/notes" + (status ? `?status=${status}` : ""), { headers: authHeader() }).then(handle),
  createNote: (body) => fetch("/api/notes", json("POST", { body })).then(handle),
  updateNote: (id, p) => fetch(`/api/notes/${id}`, json("PATCH", p)).then(handle),
  deleteNote: (id) => fetch(`/api/notes/${id}`, json("DELETE")).then(handle),
  deleteScheduled: () => fetch("/api/notes/delete-scheduled", json("POST")).then(handle),
  approve: (ids) => fetch("/api/notes/approve", json("POST", { note_ids: ids })).then(handle),
  autoSpread: (p) => fetch("/api/notes/auto-spread", json("POST", p)).then(handle),
  postNow: (id) => fetch(`/api/notes/${id}/post-now`, json("POST")).then(handle),
};
