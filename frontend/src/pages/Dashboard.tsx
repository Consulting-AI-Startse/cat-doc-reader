import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { listDocuments } from "../api/documents";
import type { DocumentListItem } from "../types/document";
import { StatusBadge } from "../components/StatusBadge";
import { NewDocumentModal } from "../components/NewDocumentModal";
import { isPending } from "../lib/status";
import { EMPTY, fmtDateTime } from "../lib/format";

function fmtNumber(v: number): string {
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(v);
}

function docTotal(item: DocumentListItem): string {
  if (item.total == null) return EMPTY;
  const n = typeof item.total === "string" ? Number(item.total) : item.total;
  return Number.isNaN(n) ? EMPTY : fmtNumber(n);
}

export function Dashboard() {
  const [modalOpen, setModalOpen] = useState(false);
  const navigate = useNavigate();

  const docs = useQuery({
    queryKey: ["documents"],
    queryFn: listDocuments,
    // Polling enquanto houver documento em processamento.
    refetchInterval: (query) => {
      const rows = query.state.data as DocumentListItem[] | undefined;
      return rows?.some((r) => isPending(r.status)) ? 3000 : false;
    },
  });

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900">Documentos</h1>
          <p className="mt-1 text-sm text-neutral-500">
            Suba um documento e acompanhe a leitura. Os números do agente estão em Performance.
          </p>
        </div>
        <button
          onClick={() => setModalOpen(true)}
          className="cursor-pointer rounded-lg bg-[#ffcd11] px-4 py-2 text-sm font-semibold text-neutral-900 shadow-sm transition-colors hover:bg-[#f0c000]"
        >
          + Novo documento
        </button>
      </div>

      <div className="overflow-hidden rounded-2xl border border-neutral-200 bg-white">
        <div className="border-b border-neutral-200 px-5 py-3">
          <h2 className="text-sm font-semibold text-neutral-700">Documentos</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-neutral-200 bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
              <tr>
                <th className="px-5 py-3 font-medium">Arquivo</th>
                <th className="px-5 py-3 font-medium">Recebido</th>
                <th className="px-5 py-3 text-center font-medium">Invoices</th>
                <th className="px-5 py-3 text-right font-medium">Total extraído</th>
                <th className="px-5 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {docs.isLoading && (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-center text-neutral-400">Carregando…</td>
                </tr>
              )}
              {docs.isError && (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-center text-red-600">Falha ao carregar documentos.</td>
                </tr>
              )}
              {docs.data?.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-center text-neutral-400">
                    Nenhum documento ainda. Clique em “Novo documento”.
                  </td>
                </tr>
              )}
              {docs.data?.map((d) => (
                <tr
                  key={d.id}
                  onClick={() => navigate(`/documents/${d.id}`)}
                  className="cursor-pointer transition-colors hover:bg-neutral-50"
                >
                  <td className="px-5 py-3 font-medium text-neutral-800">{d.source_filename ?? EMPTY}</td>
                  <td className="px-5 py-3 text-neutral-500">{fmtDateTime(d.created_at)}</td>
                  <td className="px-5 py-3 text-center tabular text-neutral-700">{d.invoice_count}</td>
                  <td className="px-5 py-3 text-right tabular text-neutral-700">{docTotal(d)}</td>
                  <td className="px-5 py-3"><StatusBadge status={d.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {modalOpen && <NewDocumentModal onClose={() => setModalOpen(false)} />}
    </div>
  );
}
