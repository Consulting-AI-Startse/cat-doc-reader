import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { getMetrics, listDocuments } from "../api/documents";
import type { DocumentListItem, Metrics } from "../types/document";
import { StatusBadge } from "../components/StatusBadge";
import { NewDocumentModal } from "../components/NewDocumentModal";
import { isPending } from "../lib/status";
import { EMPTY, fmtDateTime } from "../lib/format";

// So os campos numericos: Metrics tambem tem Duration, que nao e ReactNode.
type NumericMetric = { [K in keyof Metrics]: Metrics[K] extends number ? K : never }[keyof Metrics];

interface CardDef {
  key: NumericMetric;
  label: string;
  accent: string;
  kind?: "money";
}

const CARDS: CardDef[] = [
  { key: "documentos", label: "Documentos", accent: "text-neutral-900" },
  { key: "invoices", label: "Invoices", accent: "text-neutral-900" },
  { key: "nao_processados", label: "Não processados", accent: "text-neutral-500" },
  { key: "aguardando_revisao", label: "Aguardando revisão", accent: "text-blue-600" },
  { key: "aprovados", label: "Aprovados", accent: "text-emerald-600" },
  { key: "erros", label: "Erros", accent: "text-red-600" },
  { key: "valor_total_extraido", label: "Valor total extraído", accent: "text-neutral-900", kind: "money" },
];

// Mesmo seletor da pagina de fornecedores; a janela conta pela data de upload.
const PERIODOS = [
  { dias: 7, rotulo: "7 dias" },
  { dias: 30, rotulo: "30 dias" },
  { dias: 90, rotulo: "90 dias" },
  { dias: 0, rotulo: "Tudo" },
];

function fmtNumber(v: number): string {
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(v);
}

function fmtSeconds(v: number | null): string {
  if (v == null) return EMPTY;
  if (v < 90) return `${Math.round(v)} s`;
  if (v < 5400) return `${(v / 60).toFixed(1)} min`;
  return `${(v / 3600).toFixed(1)} h`;
}

function fmtPct(v: number | null): string {
  return v == null ? EMPTY : `${Math.round(v * 100)}%`;
}

/** Performance do agente no periodo: tempo, autonomia, acerto. */
function AgentCards({ m }: { m: Metrics | undefined }) {
  const cards = [
    {
      label: "Tempo de processamento",
      value: m ? fmtSeconds(m.processing_seconds.median) : EMPTY,
      hint: m ? `p90 ${fmtSeconds(m.processing_seconds.p90)} · ${m.processing_seconds.n} doc.` : "",
    },
    {
      label: "Upload até resultado",
      value: m ? fmtSeconds(m.turnaround_seconds.median) : EMPTY,
      hint: m ? `p90 ${fmtSeconds(m.turnaround_seconds.p90)} · ${m.turnaround_seconds.n} doc.` : "",
    },
    {
      label: "Extraídos sem revisão",
      value: m ? fmtPct(m.auto_rate) : EMPTY,
      hint: m ? `${m.auto_extracted} de ${m.terminados} terminados` : "",
    },
    {
      label: "Campos corrigidos na revisão",
      value: m ? fmtPct(m.fields_corrected_rate) : EMPTY,
      hint: m ? `${m.fields_corrected} de ${m.fields_scored} pontuados` : "",
    },
    {
      label: "Duplicatas sinalizadas",
      value: m ? String(m.duplicatas) : EMPTY,
      hint: m ? `${m.rejeitados} rejeitado(s)` : "",
    },
  ];
  return (
    <div className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
      {cards.map((c) => (
        <div key={c.label} className="rounded-2xl border border-neutral-200 bg-white p-4">
          <p className="text-xs font-medium text-neutral-500">{c.label}</p>
          <p className="mt-2 text-2xl font-semibold tabular text-neutral-900">{c.value}</p>
          <p className="mt-1 text-xs text-neutral-400">{c.hint}</p>
        </div>
      ))}
    </div>
  );
}

function docTotal(item: DocumentListItem): string {
  if (item.total == null) return EMPTY;
  const n = typeof item.total === "string" ? Number(item.total) : item.total;
  return Number.isNaN(n) ? EMPTY : fmtNumber(n);
}

export function Dashboard() {
  const [modalOpen, setModalOpen] = useState(false);
  const navigate = useNavigate();

  const [dias, setDias] = useState(30);
  const metrics = useQuery({
    queryKey: ["metrics", dias],
    queryFn: () => getMetrics(dias),
    refetchInterval: 5000,
  });
  const docs = useQuery({
    queryKey: ["documents"],
    queryFn: listDocuments,
    // Polling enquanto houver documento em processamento.
    refetchInterval: (query) => {
      const rows = query.state.data as DocumentListItem[] | undefined;
      return rows?.some((r) => isPending(r.status)) ? 3000 : false;
    },
  });

  const m = metrics.data;

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900">Dashboard</h1>
          <p className="mt-1 text-sm text-neutral-500">
            Documentos recebidos e o processamento dos invoices.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex gap-1 rounded-lg border border-neutral-200 bg-white p-0.5">
            {PERIODOS.map((p) => (
              <button
                key={p.dias}
                onClick={() => setDias(p.dias)}
                className={`cursor-pointer rounded-md px-3 py-1 text-sm font-medium ${
                  dias === p.dias ? "bg-neutral-900 text-white" : "text-neutral-600 hover:bg-neutral-50"
                }`}
              >
                {p.rotulo}
              </button>
            ))}
          </div>
          <button
            onClick={() => setModalOpen(true)}
            className="cursor-pointer rounded-lg bg-[#ffcd11] px-4 py-2 text-sm font-semibold text-neutral-900 shadow-sm transition-colors hover:bg-[#f0c000]"
          >
            + Novo documento
          </button>
        </div>
      </div>

      <div className="mb-4 grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-7">
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

      <AgentCards m={m} />

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
