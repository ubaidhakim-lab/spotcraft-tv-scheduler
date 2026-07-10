import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API });

export async function uploadPlan(file) {
  const fd = new FormData();
  fd.append("file", file);
  const res = await api.post("/plans/upload", fd, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

export async function learnSample(file) {
  const fd = new FormData();
  fd.append("file", file);
  const res = await api.post("/plans/learn-sample", fd, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

export async function generatePlan(planId, edits, prefs, rowOverrides = []) {
  const res = await api.post(`/plans/${planId}/generate`, {
    edits,
    row_overrides: rowOverrides,
    prefs,
  });
  return res.data;
}

export function downloadUrl(resultId) {
  return `${API}/results/${resultId}/download`;
}

export async function saveSession(payload) {
  const res = await api.post(`/sessions`, payload);
  return res.data;
}

export async function listSessions() {
  const res = await api.get(`/sessions`);
  return res.data;
}

export async function getSession(id) {
  const res = await api.get(`/sessions/${id}`);
  return res.data;
}

export async function deleteSession(id) {
  const res = await api.delete(`/sessions/${id}`);
  return res.data;
}
