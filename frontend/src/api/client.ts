// `||` (não `??`) para que VITE_API_BASE_URL="" (vazio no dev) caia no proxy
// "/api" do Vite. Com `??`, a string vazia passaria e quebraria as URLs.
export const apiBase = () => import.meta.env.VITE_API_BASE_URL || "/api";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, init);
  if (!res.ok) {
    // O `detail` do FastAPI é a única pista útil quando o import recusa um CSV
    // ("envie um arquivo .csv", "arquivo vazio"). Antes só subia o status, e a
    // tela mostrava "422 Unprocessable Entity" para tudo.
    let detalhe = "";
    try {
      const corpo = await res.json();
      detalhe =
        typeof corpo?.detail === "string" ? corpo.detail : JSON.stringify(corpo?.detail ?? "");
    } catch {
      // corpo não era JSON; fica só o status
    }
    throw new Error(detalhe ? `${res.status} — ${detalhe}` : `${res.status} ${res.statusText}`);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}
