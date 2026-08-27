// Estado "em andamento": mostra pulso e dispara o polling.
export function isPending(s: string): boolean {
  return s === "received" || s === "processing";
}

// Estados em que o documento pode ser editado/aprovado (revisÃ£o humana).
export function canReview(s: string): boolean {
  return s === "extracted" || s === "needs_review";
}

export function statusLabel(s: string): string {
  switch (s) {
    case "received":
      return "Recebido";
    case "processing":
      return "Processando";
    case "extracted":
      return "Para revisar";
    case "needs_review":
      return "Revisar";
    case "approved":
      return "Aprovado";
    case "rejected":
      return "Rejeitado";
    case "error":
      return "Erro";
    default:
      return s;
  }
}

// Classes Tailwind (bg/text/ring) por status, para o badge.
export function statusBadgeClasses(s: string): string {
  switch (s) {
    case "received":
    case "processing":
      return "bg-neutral-100 text-neutral-600 ring-neutral-500/20";
    case "extracted":
      return "bg-blue-50 text-blue-700 ring-blue-600/20";
    case "needs_review":
      return "bg-amber-50 text-amber-700 ring-amber-600/20";
    case "approved":
      return "bg-emerald-50 text-emerald-700 ring-emerald-600/20";
    case "rejected":
    case "error":
      return "bg-red-50 text-red-700 ring-red-600/20";
    default:
      return "bg-neutral-100 text-neutral-600 ring-neutral-500/20";
  }
}
