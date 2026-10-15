const BASE = import.meta.env.VITE_API_BASE || "/api/v1";
const TOKEN_KEY = "rcs_token";

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable: session lasts until reload */
  }
}

export class ApiError extends Error {
  constructor(status, data) {
    super(describeError(data) || `Request failed (${status})`);
    this.status = status;
    this.data = data || {};
  }
}

function describeError(data) {
  if (!data) return "";
  if (typeof data === "string") return data;
  if (data.detail) return data.detail;
  // DRF field errors: { field: ["msg"] }
  return Object.entries(data)
    .map(([field, msgs]) => `${field.replace(/_/g, " ")}: ${[].concat(msgs).join(" ")}`)
    .join(" ");
}

export async function api(path, { method = "GET", body, params } = {}) {
  const url = new URL(BASE + path, window.location.origin);
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
  });

  const headers = { Accept: "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Token ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const res = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) throw new ApiError(res.status, data);
  return data;
}

export function fieldErrors(error) {
  if (!(error instanceof ApiError) || error.status !== 400 || error.data.detail) return {};
  return Object.fromEntries(Object.entries(error.data).map(([k, v]) => [k, [].concat(v).join(" ")]));
}
