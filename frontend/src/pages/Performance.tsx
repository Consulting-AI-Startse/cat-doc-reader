import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getMetrics } from "../api/documents";
import { EMPTY } from "../lib/format";
import type { DayPoint, Metrics } from "../types/document";

// Mesmo seletor da pagina de fornecedores; a janela conta pela data de upload.
const PERIODOS = [
  { dias: 7, rotulo: "7 dias" },
  { dias: 30, rotulo: "30 dias" },
  { dias: 90, rotulo: "90 dias" },
  { dias: 0, rotulo: "Tudo" },
];

// Uma cor por desfecho, a mesma nos cards, na barra e na legenda.
const SERIES = [
  { key: "auto", rotulo: "Extraído sem revisão", cor: "#059669" },
  { key: "review", rotulo: "Foi para revisão", cor: "#2563eb" },
  { key: "error", rotulo: "Erro", cor: "#dc2626" },
  { key: "pending", rotulo: "Em processamento", cor: "#a3a3a3" },
] as const;

function fmtNumber(v: number): string {
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(v);
}

/** "5,89 mi": o valor cheio nao cabe no card de 7 colunas. O cheio fica no title. */
function fmtCompact(v: number): string {
  return new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 2 }).format(v);
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

function fmtDay(iso: string): string {
  const [, m, d] = iso.split("-");
  return `${d}/${m}`;
}

function Card({ label, value, hint, title, accent = "text-neutral-900" }: {
  label: string;
  value: string;
  hint?: string;
  title?: string;
  accent?: string;
}) {
  return (
    <div className="min-w-0 rounded-2xl border border-neutral-200 bg-white p-4" title={title}>
      <p className="text-xs font-medium text-neutral-500">{label}</p>
      <p className={`mt-2 truncate text-2xl font-semibold tabular ${accent}`}>{value}</p>
      {hint && <p className="mt-1 text-xs text-neutral-400">{hint}</p>}
    </div>
  );
}

/** Rotulo do eixo x so a cada N dias: 90 rotulos nao cabem. */
function labelStep(n: number): number {
  if (n <= 10) return 1;
  if (n <= 31) return 5;
  if (n <= 92) return 14;
  return 30;
}

/** Barras empilhadas por dia, em SVG puro: o CI da CAT so instala o que esta
 *  no lock, e uma biblioteca de grafico seria dependencia nova no Artifactory
 *  so para isto. */
function DailyBars({ series }: { series: DayPoint[] }) {
  const W = 960;
  const H = 220;
  const pad = { l: 32, r: 8, t: 8, b: 24 };
  const max = Math.max(1, ...series.map((p) => p.received));
  const slot = (W - pad.l - pad.r) / Math.max(1, series.length);
  const barW = Math.max(2, Math.min(28, slot * 0.7));
  const y = (v: number) => pad.t + (H - pad.t - pad.b) * (1 - v / max);
  const step = labelStep(series.length);
  const ticks = max <= 4 ? Array.from({ length: max + 1 }, (_, i) => i) : [0, Math.round(max / 2), max];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-56 w-full" role="img" aria-label="Documentos por dia">
      {ticks.map((t) => (
        <g key={t}>
          <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} stroke="#e5e5e5" />
          <text x={pad.l - 6} y={y(t) + 4} textAnchor="end" fontSize="11" fill="#a3a3a3">{t}</text>
        </g>
      ))}
      {series.map((p, i) => {
        const x = pad.l + slot * i + (slot - barW) / 2;
        let base = 0;
        return (
          <g key={p.date}>
            <title>
              {`${fmtDay(p.date)}: ${p.received} documento(s)\n` +
                SERIES.map((s) => `${s.rotulo}: ${p[s.key]}`).join("\n") +
                (p.not_invoice ? `\nProvavelmente não é invoice: ${p.not_invoice}` : "") +
                (p.processing_median != null ? `\nTempo mediano: ${fmtSeconds(p.processing_median)}` : "")}
            </title>
            {/* Retangulo transparente da altura toda: o tooltip funciona no dia vazio tambem. */}
            <rect x={pad.l + slot * i} y={pad.t} width={slot} height={H - pad.t - pad.b} fill="transparent" />
            {SERIES.map((s) => {
              const v = p[s.key];
              if (!v) return null;
              const top = y(base + v);
              const h = y(base) - top;
              base += v;
              return <rect key={s.key} x={x} y={top} width={barW} height={h} fill={s.cor} rx={1.5} />;
            })}
            {i % step === 0 && (
              <text x={x + barW / 2} y={H - 6} textAnchor="middle" fontSize="11" fill="#737373">
                {fmtDay(p.date)}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

/** Tempo mediano de processamento por dia. Dia sem documento interrompe a
 *  linha em vez de cair a zero: zero seria um tempo, e nao ha tempo nenhum. */
function DailyTime({ series }: { series: DayPoint[] }) {
  const W = 960;
  const H = 140;
  const pad = { l: 48, r: 8, t: 10, b: 24 };
  const valores = series.map((p) => p.processing_median).filter((v): v is number => v != null);
  if (valores.length === 0) {
    return <p className="py-8 text-center text-sm text-neutral-400">Nenhum documento terminado no período.</p>;
  }
  const max = Math.max(...valores) * 1.1 || 1;
  const slot = (W - pad.l - pad.r) / Math.max(1, series.length);
  const x = (i: number) => pad.l + slot * i + slot / 2;
  const y = (v: number) => pad.t + (H - pad.t - pad.b) * (1 - v / max);
  const step = labelStep(series.length);

  // Um trecho por sequencia de dias com valor.
  const trechos: string[] = [];
  let atual: string[] = [];
  series.forEach((p, i) => {
    if (p.processing_median == null) {
      if (atual.length) trechos.push(atual.join(" "));
      atual = [];
    } else {
      atual.push(`${x(i)},${y(p.processing_median)}`);
    }
  });
  if (atual.length) trechos.push(atual.join(" "));

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-36 w-full" role="img" aria-label="Tempo mediano por dia">
      {[0, max / 2, max].map((t) => (
        <g key={t}>
          <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} stroke="#e5e5e5" />
          <text x={pad.l - 6} y={y(t) + 4} textAnchor="end" fontSize="11" fill="#a3a3a3">{fmtSeconds(t)}</text>
        </g>
      ))}
      {trechos.map((pts, k) => (
        <polyline key={k} points={pts} fill="none" stroke="#171717" strokeWidth={2} />
      ))}
      {series.map((p, i) =>
        p.processing_median == null ? null : (
          <circle key={p.date} cx={x(i)} cy={y(p.processing_median)} r={3} fill="#171717">
            <title>{`${fmtDay(p.date)}: ${fmtSeconds(p.processing_median)}`}</title>
          </circle>
        ),
      )}
      {series.map((p, i) =>
        i % step === 0 ? (
          <text key={p.date} x={x(i)} y={H - 6} textAnchor="middle" fontSize="11" fill="#737373">
            {fmtDay(p.date)}
          </text>
        ) : null,
      )}
    </svg>
  );
}

export function Performance() {
  const [dias, setDias] = useState(30);
  const { data, isLoading, isError } = useQuery({
    queryKey: ["metrics", dias],
    queryFn: () => getMetrics(dias),
    refetchInterval: 10000,
  });
  const m: Metrics | undefined = data;

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900">Performance do agente</h1>
          <p className="mt-1 text-sm text-neutral-500">
            Quanto o agente resolve sozinho, em quanto tempo, e quanto o revisor precisa corrigir. O período
            conta pela data de upload.
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

      {isLoading && <p className="text-neutral-400">Carregando…</p>}
      {isError && <p className="text-red-600">Falha ao carregar as métricas.</p>}

      {m && (
        <>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">O agente</h2>
          <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
            <Card
              label="Extraídos sem revisão"
              value={fmtPct(m.auto_rate)}
              hint={`${m.auto_extracted} de ${m.terminados} terminados`}
              accent="text-emerald-600"
            />
            <Card
              label="Tempo de processamento"
              value={fmtSeconds(m.processing_seconds.median)}
              hint={`mediana · p90 ${fmtSeconds(m.processing_seconds.p90)}`}
            />
            <Card
              label="Upload até resultado"
              value={fmtSeconds(m.turnaround_seconds.median)}
              hint={`mediana · p90 ${fmtSeconds(m.turnaround_seconds.p90)}`}
            />
            <Card
              label="Campos corrigidos na revisão"
              value={fmtPct(m.fields_corrected_rate)}
              hint={`${m.fields_corrected} de ${m.fields_scored} lidos`}
            />
            <Card label="Duplicatas sinalizadas" value={String(m.duplicatas)} accent="text-amber-600" />
            <Card
              label="Provavelmente não é invoice"
              value={String(m.nao_invoice)}
              hint="documentos marcados em vermelho"
              accent="text-red-600"
            />
          </div>

          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">Volume</h2>
          <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-7">
            <Card label="Documentos" value={String(m.documentos)} />
            <Card label="Invoices" value={String(m.invoices)} />
            <Card label="Em processamento" value={String(m.nao_processados)} accent="text-neutral-500" />
            <Card label="Aguardando revisão" value={String(m.aguardando_revisao)} accent="text-blue-600" />
            <Card label="Aprovados" value={String(m.aprovados)} accent="text-emerald-600" />
            <Card label="Erros" value={String(m.erros)} accent="text-red-600" />
            <Card
              label="Valor total extraído"
              value={fmtCompact(m.valor_total_extraido)}
              title={fmtNumber(m.valor_total_extraido)}
              hint="sem cópia, rejeitado ou erro"
            />
          </div>

          <div className="mb-6 rounded-2xl border border-neutral-200 bg-white p-5">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-sm font-semibold text-neutral-700">Documentos por dia</h2>
              <div className="flex flex-wrap gap-4 text-xs text-neutral-600">
                {SERIES.map((s) => (
                  <span key={s.key} className="flex items-center gap-1.5">
                    <span className="h-2.5 w-2.5 rounded-sm" style={{ background: s.cor }} />
                    {s.rotulo}
                  </span>
                ))}
              </div>
            </div>
            {m.series.length === 0 ? (
              <p className="py-8 text-center text-sm text-neutral-400">Nenhum documento no período.</p>
            ) : (
              <DailyBars series={m.series} />
            )}
          </div>

          <div className="rounded-2xl border border-neutral-200 bg-white p-5">
            <h2 className="mb-3 text-sm font-semibold text-neutral-700">
              Tempo mediano de processamento por dia
            </h2>
            <DailyTime series={m.series} />
          </div>
        </>
      )}
    </div>
  );
}
