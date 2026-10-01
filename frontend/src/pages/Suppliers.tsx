import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { getSupplierDetail, getSupplierReport } from "../api/suppliers";
import { StatusBadge } from "../components/StatusBadge";
import { EMPTY, fmtDate } from "../lib/format";
import { pct } from "../lib/confidence";
import type { DocumentStatus } from "../types/document";
import type { SupplierRow } from "../types/suppliers";

const PERIODOS = [
  { dias: 30, rotulo: "30 dias" },
  { dias: 90, rotulo: "90 dias" },
  { dias: 0, rotulo: "Tudo" },
];

const CAMPO: Record<string, string> = {
  invoice_number: "Nº invoice",
  total: "Total da invoice",
  part_number: "Part #",
  purchase_order: "PO",
  quantity: "Quantidade",
  unit_price: "Unitário",
  amount: "Total da linha",
  serial_number: "Serial",
};

type Ordem = "mean_confidence" | "flagged_rate" | "correction_rate" | "invoices";

/** Barra em CSS: sem biblioteca de gráfico, o CI só instala o que está no lock. */
function Barra({ valor }: { valor: number | null }) {
  if (valor == null) return <span className="text-neutral-400">sem nota</span>;
  const cor = valor < 0.85 ? "bg-amber-500" : valor < 0.95 ? "bg-neutral-400" : "bg-emerald-500";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 rounded-full bg-neutral-100">
        <div className={`h-1.5 rounded-full ${cor}`} style={{ width: `${Math.round(valor * 100)}%` }} />
      </div>
      <span className="tabular text-neutral-700">{pct(valor)}</span>
    </div>
  );
}

function Detalhe({ chave, dias }: { chave: string | null; dias: number }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["supplier-detail", chave, dias],
    queryFn: () => getSupplierDetail(chave, dias),
  });
  if (isLoading) return <p className="p-4 text-xs text-neutral-400">Carregando…</p>;
  if (isError || !data) return <p className="p-4 text-xs text-red-600">Falha ao carregar o detalhe.</p>;

  return (
    <div className="grid gap-6 bg-neutral-50 p-4 lg:grid-cols-2">
      <div>
        <p className="text-xs font-medium text-neutral-600">Por campo — o que mais dá trabalho primeiro</p>
        {data.fields.length === 0 ? (
          <p className="mt-2 text-xs text-neutral-400">Nenhuma invoice com nota por campo neste período.</p>
        ) : (
          <table className="mt-2 w-full text-left text-xs">
            <thead className="text-[11px] uppercase tracking-wide text-neutral-400">
              <tr>
                <th className="py-1 pr-2 font-medium">Campo</th>
                <th className="py-1 pr-2 text-right font-medium">Lidos</th>
                <th className="py-1 pr-2 text-right font-medium" title="confiança do OCR abaixo do limite">Fracos</th>
                <th className="py-1 pr-2 text-right font-medium" title="o documento traz o valor com um caractere trocado">Ambíguos</th>
                <th className="py-1 pr-2 text-right font-medium" title="o valor não aparece no texto">Não achados</th>
                <th className="py-1 pr-2 text-right font-medium">Corrigidos</th>
                <th className="py-1 font-medium">Nota média</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-200">
              {data.fields.map((f) => (
                <tr key={f.field}>
                  <td className="py-1 pr-2 text-neutral-800">{CAMPO[f.field] ?? f.field}</td>
                  <td className="py-1 pr-2 text-right tabular text-neutral-600">{f.scored}</td>
                  <td className="py-1 pr-2 text-right tabular text-neutral-600">{f.low || EMPTY}</td>
                  <td className="py-1 pr-2 text-right tabular text-neutral-600">{f.ambiguous || EMPTY}</td>
                  <td className="py-1 pr-2 text-right tabular text-neutral-600">{f.not_located || EMPTY}</td>
                  <td className="py-1 pr-2 text-right tabular text-neutral-600">{f.corrected || EMPTY}</td>
                  <td className="py-1"><Barra valor={f.mean_score} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <div>
        <p className="text-xs font-medium text-neutral-600">Invoices</p>
        <table className="mt-2 w-full text-left text-xs">
          <tbody className="divide-y divide-neutral-200">
            {data.invoices.map((inv) => (
              <tr key={inv.invoice_id}>
                <td className="py-1 pr-2">
                  <Link to={`/documents/${inv.document_id}`} className="font-mono text-neutral-800 underline-offset-2 hover:underline">
                    {inv.invoice_number || EMPTY}
                  </Link>
                </td>
                <td className="py-1 pr-2 text-neutral-500">{fmtDate(inv.created_at)}</td>
                <td className="py-1 pr-2"><StatusBadge status={inv.document_status as DocumentStatus} /></td>
                <td className="py-1 pr-2 tabular text-neutral-600" title="pior campo · média">
                  {inv.min_field_confidence == null
                    ? "sem nota"
                    : `${pct(inv.min_field_confidence)} · ${pct(inv.mean_field_confidence)}`}
                </td>
                <td className="py-1 text-amber-700">
                  {(inv.flagged_fields ?? 0) > 0 ? `${inv.flagged_fields} a conferir` : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function Suppliers() {
  const [dias, setDias] = useState(30);
  const [ordem, setOrdem] = useState<Ordem>("mean_confidence");
  const [aberto, setAberto] = useState<string | null | undefined>(undefined);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["supplier-report", dias],
    queryFn: () => getSupplierReport(dias),
  });

  // Pior primeiro em todas as colunas: a tela existe para achar quem dá trabalho.
  const linhas = useMemo(() => {
    const rows = [...(data?.suppliers ?? [])];
    const val = (r: SupplierRow) => r[ordem];
    rows.sort((a, b) => {
      const va = val(a);
      const vb = val(b);
      if (va == null) return vb == null ? 0 : 1;
      if (vb == null) return -1;
      return ordem === "mean_confidence" ? va - vb : vb - va;
    });
    return rows;
  }, [data, ordem]);

  const comNota = linhas.filter((l) => l.invoices_scored > 0);
  const semNota = linhas.reduce((n, l) => n + (l.invoices - l.invoices_scored), 0);

  const cabecalho = (rotulo: string, chave: Ordem | null, dica?: string) => (
    <th
      className={`py-2 pr-3 font-medium ${chave ? "cursor-pointer hover:text-neutral-700" : ""} ${
        chave === ordem ? "text-neutral-800" : ""
      }`}
      title={dica}
      onClick={chave ? () => setOrdem(chave) : undefined}
    >
      {rotulo}
    </th>
  );

  return (
    <main className="mx-auto max-w-7xl px-6 py-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-neutral-900">Confiança por fornecedor</h1>
          <p className="mt-1 text-sm text-neutral-500">
            Nota do OCR por campo extraído, agregada por fornecedor. Documentos rejeitados ou com erro e
            cópias de duplicata não entram.
          </p>
        </div>
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
      </div>

      {isLoading && <p className="mt-8 text-neutral-400">Carregando…</p>}
      {isError && <p className="mt-8 text-red-600">Falha ao carregar o relatório.</p>}

      {data && linhas.length === 0 && (
        <p className="mt-8 rounded-xl border border-neutral-200 bg-white p-6 text-sm text-neutral-500">
          Nenhuma invoice no período.
        </p>
      )}

      {data && linhas.length > 0 && (
        <>
          <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
            {[
              ["Fornecedores", String(linhas.length)],
              ["Com nota por campo", String(comNota.length)],
              ["Invoices sem nota", String(semNota)],
              [
                "Abaixo de 85% na média",
                String(comNota.filter((l) => (l.mean_confidence ?? 1) < 0.85).length),
              ],
            ].map(([rotulo, valor]) => (
              <div key={rotulo} className="rounded-xl border border-neutral-200 bg-white p-4">
                <p className="text-xs font-medium uppercase tracking-wide text-neutral-400">{rotulo}</p>
                <p className="mt-1 text-lg font-semibold text-neutral-900">{valor}</p>
              </div>
            ))}
          </div>

          <div className="mt-6 overflow-x-auto rounded-xl border border-neutral-200 bg-white">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-neutral-200 text-[11px] uppercase tracking-wide text-neutral-400">
                <tr>
                  <th className="py-2 pl-4 pr-3 font-medium">Fornecedor</th>
                  {cabecalho("Invoices", "invoices", "com nota / total")}
                  {cabecalho("Confiança média", "mean_confidence")}
                  <th className="py-2 pr-3 font-medium" title="a pior nota de campo no período">Pior campo</th>
                  {cabecalho("A conferir", "flagged_rate", "invoices com algum campo marcado")}
                  {cabecalho("Corrigidos", "correction_rate", "campos corrigidos na revisão / campos lidos")}
                  <th className="py-2 pr-3 font-medium">Campo mais fraco</th>
                  <th className="py-2 pr-4 font-medium">Último</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {linhas.map((l) => {
                  const chave = l.supplier_key ?? "\u0000";
                  const expandido = aberto === chave;
                  return (
                    <FragmentoLinha
                      key={chave}
                      linha={l}
                      expandido={expandido}
                      onToggle={() => setAberto(expandido ? undefined : chave)}
                      dias={dias}
                    />
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </main>
  );
}

function FragmentoLinha({
  linha: l,
  expandido,
  onToggle,
  dias,
}: {
  linha: SupplierRow;
  expandido: boolean;
  onToggle: () => void;
  dias: number;
}) {
  return (
    <>
      <tr className="cursor-pointer hover:bg-neutral-50" onClick={onToggle}>
        <td className="py-2 pl-4 pr-3 font-medium text-neutral-900">
          <span className="mr-1.5 inline-block w-3 text-neutral-400">{expandido ? "▾" : "▸"}</span>
          {l.supplier || "(sem fornecedor)"}
        </td>
        <td className="py-2 pr-3 tabular text-neutral-600">
          {l.invoices_scored === l.invoices ? l.invoices : `${l.invoices_scored} / ${l.invoices}`}
        </td>
        <td className="py-2 pr-3"><Barra valor={l.mean_confidence} /></td>
        <td className="py-2 pr-3 tabular text-neutral-600">{pct(l.min_confidence)}</td>
        <td className="py-2 pr-3 tabular text-neutral-600">
          {l.invoices_scored ? `${l.flagged_invoices} (${pct(l.flagged_rate)})` : EMPTY}
        </td>
        <td className="py-2 pr-3 tabular text-neutral-600">
          {l.fields_scored ? `${l.fields_corrected} de ${l.fields_scored}` : EMPTY}
        </td>
        <td className="py-2 pr-3 text-neutral-600">{l.weakest_field ? CAMPO[l.weakest_field] ?? l.weakest_field : EMPTY}</td>
        <td className="py-2 pr-4 text-neutral-500">{fmtDate(l.last_seen)}</td>
      </tr>
      {expandido && (
        <tr>
          <td colSpan={8} className="p-0">
            <Detalhe chave={l.supplier_key} dias={dias} />
          </td>
        </tr>
      )}
    </>
  );
}
