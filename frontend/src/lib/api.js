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

export async function generatePlan(planId, edits, prefs) {
  const res = await api.post(`/plans/${planId}/generate`, { edits, prefs });
  return res.data;
}

export function downloadUrl(resultId) {
  return `${API}/results/${resultId}/download`;
}
