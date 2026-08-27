// `||` (nÃ£o `??`) para que VITE_API_BASE_URL="" (vazio no dev) caia no proxy
// "/api" do Vite. Com `??`, a string vazia passaria e quebraria as URLs.
export const apiBase = () => import.meta.env.VITE_API_BASE_URL || "/api";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, init);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.status === 204 ? (undefined as T) : res.json();
}
