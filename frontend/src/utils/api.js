export const getToken   = ()  => localStorage.getItem("stt_token");
export const setToken   = (t) => localStorage.setItem("stt_token", t);
export const clearToken = ()  => localStorage.removeItem("stt_token");

export async function apiFetch(url, options = {}) {
  const token   = getToken();
  const headers = { ...options.headers };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(url, { ...options, headers });

  if (res.status === 401) {
    clearToken();
    window.dispatchEvent(new Event("stt:logout"));
  }
  return res;
}

/** Build an SSE URL with the JWT appended as ?token= */
export function sseUrl(path) {
  const token = getToken();
  if (!token) return path;
  const sep = path.includes("?") ? "&" : "?";
  return `${path}${sep}token=${encodeURIComponent(token)}`;
}
