import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { getMetrics, listDocuments } from "../api/documents";
import type { DocumentListItem, Metrics } from "../types/document";
import { StatusBadge } from "../components/StatusBadge";
import { NewDocumentModal } from "../components/NewDocumentModal";
import { isPending } from "../lib/status";
import { EMPTY, fmtDateTime } from "../lib/format";

interface CardDef {
  key: keyof Metrics;
  label: string;
  accent: string;
  kind?: "money";
}

const CARDS: CardDef[] = [
  { key: "documentos", label: "Documentos", accent: "text-neutral-900" },
  { key: "invoices", label: "Invoices", accent: "text-neutral-900" },
  { key: "nao_processados", label: "NÃ£o processados", accent: "text-neutral-500" },
  { key: "aguardando_revisao", label: "Aguardando revisÃ£o", accent: "text-blue-600" },
  { key: "aprovados", label: "Aprovados", accent: "text-emerald-600" },
  { key: "valor_total_extraido", label: "Valor total extraÃ­do", accent: "text-neutral-900", kind: "money" },
];

function fmtNumber(v: number): string {
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(v);
}

function docTotal(item: DocumentListItem): string {
  if (https://urldefense.com/v3/__http://item.total__;!!FtR4BK4x7WL3xYs!7eSSCyFCjijlvTkq-nDu909aQ9KdSXixKzvq48ylXTbbOengh8CYIN7SlKKLdmZHwzuwWFqZehJczqewt09E$  == null) return EMPTY;
  const n = typeof https://urldefense.com/v3/__http://item.total__;!!FtR4BK4x7WL3xYs!7eSSCyFCjijlvTkq-nDu909aQ9KdSXixKzvq48ylXTbbOengh8CYIN7SlKKLdmZHwzuwWFqZehJczqewt09E$  === "string" ? Number(https://urldefense.com/v3/__http://item.total__;!!FtR4BK4x7WL3xYs!7eSSCyFCjijlvTkq-nDu909aQ9KdSXixKzvq48ylXTbbOengh8CYIN7SlKKLdmZHwzuwWFqZehJczqewt09E$ ) : https://urldefense.com/v3/__http://item.total__;!!FtR4BK4x7WL3xYs!7eSSCyFCjijlvTkq-nDu909aQ9KdSXixKzvq48ylXTbbOengh8CYIN7SlKKLdmZHwzuwWFqZehJczqewt09E$ ;
  return Number.isNaN(n) ? EMPTY : fmtNumber(n);
}

export function Dashboard() {
  const [modalOpen, setModalOpen] = useState(false);
  const navigate = useNavigate();

  const metrics = useQuery({ queryKey: ["metrics"], queryFn: getMetrics, refetchInterval: 5000 });
  const docs = useQuery({
    queryKey: ["documents"],
    queryFn: listDocuments,
    // Polling enquanto houver documento em processamento.
    refetchInterval: (query) => {
      const rows = https://urldefense.com/v3/__http://query.state.data__;!!FtR4BK4x7WL3xYs!7eSSCyFCjijlvTkq-nDu909aQ9KdSXixKzvq48ylXTbbOengh8CYIN7SlKKLdmZHwzuwWFqZehJczn4kielF$  as DocumentListItem[] | undefined;
      return rows?.some((r) => isPending(r.status)) ? 3000 : false;
    },
  });

  const m = https://urldefense.com/v3/__http://metrics.data__;!!FtR4BK4x7WL3xYs!7eSSCyFCjijlvTkq-nDu909aQ9KdSXixKzvq48ylXTbbOengh8CYIN7SlKKLdmZHwzuwWFqZehJczriOkRLT$ ;

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900">Dashboard</h1>
          <p className="mt-1 text-sm text-neutral-500">
            Documentos recebidos e o processamento dos invoices.
          </p>
        </div>
        <button
          onClick={() => setModalOpen(true)}
          className="cursor-pointer rounded-lg bg-[#ffcd11] px-4 py-2 text-sm font-semibold text-neutral-900 shadow-sm transition-colors hover:bg-[#f0c000]"
        >
          + Novo documento
        </button>
      </div>

      {/* MÃ©tricas */}
      <div className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
        {CARDS.map((c) => {
          const value = m ? m[c.key] : null;
          return (
            <div key={c.key} className="rounded-2xl border border-neutral-200 bg-white p-4">
              <p className="text-xs font-medium text-neutral-500">{c.label}</p>
              <p className={`mt-2 text-2xl font-semibold tabular ${c.accent}`}>
                {value == null ? EMPTY : c.kind === "money" ? fmtNumber(value) : value}
              </p>
            </div>
          );
        })}
      </div>

      {/* Tabela de documentos */}
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
                <th className="px-5 py-3 text-right font-medium">Total extraÃ­do</th>
                <th className="px-5 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {docs.isLoading && (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-center text-neutral-400">Carregandoâ€¦</td>
                </tr>
              )}
              {docs.isError && (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-center text-red-600">Falha ao carregar documentos.</td>
                </tr>
              )}
              {https://urldefense.com/v3/__http://docs.data?.length__;!!FtR4BK4x7WL3xYs!7eSSCyFCjijlvTkq-nDu909aQ9KdSXixKzvq48ylXTbbOengh8CYIN7SlKKLdmZHwzuwWFqZehJczpSsOEQr$  === 0 && (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-center text-neutral-400">
                    Nenhum documento ainda. Clique em â€œNovo documentoâ€.
                  </td>
                </tr>
              )}
              {https://urldefense.com/v3/__http://docs.data?.map((d)__;!!FtR4BK4x7WL3xYs!7eSSCyFCjijlvTkq-nDu909aQ9KdSXixKzvq48ylXTbbOengh8CYIN7SlKKLdmZHwzuwWFqZehJczmpGeo1E$  => (
                <tr
                  key={https://urldefense.com/v3/__http://d.id__;!!FtR4BK4x7WL3xYs!7eSSCyFCjijlvTkq-nDu909aQ9KdSXixKzvq48ylXTbbOengh8CYIN7SlKKLdmZHwzuwWFqZehJczlLnDPfd$ }
                  onClick={() => navigate(`/documents/${https://urldefense.com/v3/__http://d.id__;!!FtR4BK4x7WL3xYs!7eSSCyFCjijlvTkq-nDu909aQ9KdSXixKzvq48ylXTbbOengh8CYIN7SlKKLdmZHwzuwWFqZehJczlLnDPfd$ }`)}
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
