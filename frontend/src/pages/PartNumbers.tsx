import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getPartsStats,
  getSerialRules,
  importParts,
  previewSerialRules,
  putSerialRules,
} from "../api/parts";
import { FileUpload } from "../components/FileUpload";
import type { ImportResult, RulesPreview } from "../types/parts";

const num = (n: number) => n.toLocaleString("pt-BR");

/** Campo de lista: o usuário digita, dá Enter, e o valor vira uma etiqueta. */
function ListaEditavel({
  titulo,
  ajuda,
  exemplo,
  valores,
  onChange,
}: {
  titulo: string;
  ajuda: string;
  exemplo: string;
  valores: string[];
  onChange: (v: string[]) => void;
}) {
  const [rascunho, setRascunho] = useState("");

  function adicionar() {
    const v = rascunho.trim();
    if (!v) return;
    // Repetir não quebra nada no banco, mas polui a tela e o diff da regra.
    if (!valores.some((x) => x.toUpperCase() === v.toUpperCase())) onChange([...valores, v]);
    setRascunho("");
  }

  return (
    <div>
      <h3 className="text-sm font-semibold text-neutral-900">{titulo}</h3>
      <p className="mt-1 text-xs text-neutral-500">{ajuda}</p>
      <div className="mt-3 flex gap-2">
        <input
          value={rascunho}
          onChange={(e) => setRascunho(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              adicionar();
            }
          }}
          placeholder={exemplo}
          className="flex-1 rounded-lg border border-neutral-300 px-3 py-1.5 text-sm outline-none focus:border-neutral-900"
        />
        <button
          onClick={adicionar}
          disabled={!rascunho.trim()}
          className="cursor-pointer rounded-lg border border-neutral-300 bg-white px-3 py-1.5 text-sm font-medium text-neutral-700 hover:bg-neutral-50 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Adicionar
        </button>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {valores.length === 0 && (
          <span className="text-xs text-neutral-400">Nenhum — nada é marcado por aqui.</span>
        )}
        {valores.map((v) => (
          <span
            key={v}
            className="inline-flex items-center gap-1.5 rounded-full bg-neutral-100 py-1 pl-3 pr-1.5 font-mono text-xs text-neutral-800"
          >
            {v}
            <button
              onClick={() => onChange(valores.filter((x) => x !== v))}
              title="Remover"
              className="cursor-pointer rounded-full px-1 text-neutral-400 hover:bg-neutral-200 hover:text-neutral-900"
            >
              ×
            </button>
          </span>
        ))}
      </div>
    </div>
  );
}

function RelatorioImport({ r }: { r: ImportResult }) {
  const problema = r.erros.length > 0 || r.duplicadas_no_arquivo > 0;
  return (
    <div
      className={`mt-4 rounded-xl border p-4 text-sm ${
        problema ? "border-amber-300 bg-amber-50" : "border-emerald-200 bg-emerald-50"
      }`}
    >
      <p className="font-medium text-neutral-900">
        {num(r.gravadas)} de {num(r.recebidas)} linhas importadas
      </p>
      {/* recebidas = gravadas + duplicadas + erros. Mostrar as três fecha a
          conta na tela; "ignoradas" sozinho deixa o revisor sem explicação. */}
      <ul className="mt-2 space-y-0.5 text-xs text-neutral-600">
        <li>{num(r.total_na_lista)} peças na lista agora</li>
        <li>{num(r.requires_serial)} marcadas como "exige serial" pela regra atual</li>
        {r.duplicadas_no_arquivo > 0 && (
          <li>{num(r.duplicadas_no_arquivo)} repetidas dentro do próprio arquivo (a última venceu)</li>
        )}
      </ul>
      {r.erros.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-medium text-amber-900">
            {r.erros.length} linha(s) recusada(s):
          </p>
          <ul className="mt-1 space-y-0.5 font-mono text-xs text-amber-800">
            {r.erros.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export function PartNumbers() {
  const qc = useQueryClient();
  const stats = useQuery({ queryKey: ["parts-stats"], queryFn: getPartsStats });
  const regras = useQuery({ queryKey: ["serial-rules"], queryFn: getSerialRules });

  const [substrings, setSubstrings] = useState<string[]>([]);
  const [manuais, setManuais] = useState<string[]>([]);
  const [previa, setPrevia] = useState<RulesPreview | null>(null);
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [relatorio, setRelatorio] = useState<ImportResult | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  // Carrega o que está salvo uma vez; daí em diante o estado local manda.
  useEffect(() => {
    if (regras.data) {
      setSubstrings(regras.data.substrings);
      setManuais(regras.data.manual_part_numbers);
    }
  }, [regras.data]);

  const sujo = useMemo(() => {
    if (!regras.data) return false;
    const igual = (a: string[], b: string[]) =>
      a.length === b.length && a.every((x, i) => x === b[i]);
    return (
      !igual(substrings, regras.data.substrings) ||
      !igual(manuais, regras.data.manual_part_numbers)
    );
  }, [substrings, manuais, regras.data]);

  // Prévia com atraso: cada tecla dispararia uma consulta que varre 206 mil
  // linhas. 400 ms é o suficiente para esperar a pessoa terminar de digitar.
  useEffect(() => {
    if (!regras.data) return;
    const t = setTimeout(() => {
      previewSerialRules(substrings, manuais).then(setPrevia).catch(() => setPrevia(null));
    }, 400);
    return () => clearTimeout(t);
  }, [substrings, manuais, regras.data]);

  const salvar = useMutation({
    mutationFn: () => putSerialRules(substrings, manuais),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["serial-rules"] });
      qc.invalidateQueries({ queryKey: ["parts-stats"] });
      setErro(null);
    },
    onError: (e: Error) => setErro(e.message),
  });

  const importar = useMutation({
    mutationFn: (f: File) => importParts(f),
    onSuccess: (r) => {
      setRelatorio(r);
      setArquivo(null);
      setErro(null);
      qc.invalidateQueries({ queryKey: ["parts-stats"] });
      qc.invalidateQueries({ queryKey: ["serial-rules"] });
    },
    onError: (e: Error) => setErro(e.message),
  });

  const hoje = previa?.marcadas_hoje ?? regras.data?.marcadas ?? 0;
  const depois = previa?.marcadas ?? hoje;
  const delta = depois - hoje;

  return (
    <main className="mx-auto max-w-5xl px-6 py-8">
      <h1 className="text-xl font-semibold text-neutral-900">Part numbers liberados</h1>
      <p className="mt-1 text-sm text-neutral-500">
        A lista é a fonte da verdade: o que não está nela não é part number.
      </p>

      <div className="mt-6 grid grid-cols-3 gap-4">
        {[
          ["Na lista", num(stats.data?.total ?? 0)],
          ["Exigem serial", num(stats.data?.requires_serial ?? 0)],
          [
            "Último import",
            stats.data?.ultimo_import?.batch ?? "—",
          ],
        ].map(([rotulo, valor]) => (
          <div key={rotulo} className="rounded-xl border border-neutral-200 bg-white p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-neutral-400">{rotulo}</p>
            <p className="mt-1 truncate text-lg font-semibold text-neutral-900" title={String(valor)}>
              {valor}
            </p>
          </div>
        ))}
      </div>

      {erro && (
        <div className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{erro}</div>
      )}

      <section className="mt-8 rounded-xl border border-neutral-200 bg-white p-5">
        <h2 className="text-sm font-semibold text-neutral-900">Importar a lista</h2>
        <p className="mt-1 text-xs text-neutral-500">
          CSV com duas colunas: part number e nome da peça. O import é cumulativo — peça que já
          existe tem o nome atualizado, e nada é apagado.
        </p>
        <div className="mt-4">
          <FileUpload
            file={arquivo}
            onFile={setArquivo}
            onClear={() => setArquivo(null)}
            accept=".csv"
            ext="csv"
            rotulo="Arraste o CSV aqui"
            dica="Duas colunas: part number e nome. Cabeçalho é opcional."
            preview={false}
          />
        </div>
        {arquivo && (
          <button
            onClick={() => importar.mutate(arquivo)}
            disabled={importar.isPending}
            className="mt-4 cursor-pointer rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {importar.isPending ? "Importando…" : "Importar"}
          </button>
        )}
        {importar.isPending && (
          <p className="mt-2 text-xs text-neutral-500">
            A planilha completa tem 206 mil linhas e leva cerca de 17 segundos.
          </p>
        )}
        {relatorio && <RelatorioImport r={relatorio} />}
      </section>

      <section className="mt-6 rounded-xl border border-neutral-200 bg-white p-5">
        <h2 className="text-sm font-semibold text-neutral-900">Quem exige serial number</h2>
        <p className="mt-1 text-xs text-neutral-500">
          A marcação não vem na planilha. Ela sai destas duas regras, aplicadas sobre a lista
          inteira toda vez que você salvar.
        </p>

        <div className="mt-5 grid gap-6 sm:grid-cols-2">
          <ListaEditavel
            titulo="Trechos no nome da peça"
            ajuda="Marca toda peça cujo nome contenha o trecho. Não diferencia maiúscula."
            exemplo="ENGINE AR"
            valores={substrings}
            onChange={setSubstrings}
          />
          <ListaEditavel
            titulo="Part numbers avulsos"
            ajuda="Para o que nenhum trecho pega. O hífen é ignorado: 5P-1465 e 5P1465 são o mesmo."
            exemplo="6526886"
            valores={manuais}
            onChange={setManuais}
          />
        </div>

        {/* A prévia é o que torna a configuração segura. 'ENGINE' marca 910
            peças e quase todas são acessório -- FILM-ENGINE OIL, CHART-ENGINE.
            'ENGINE AR' marca 588 sem nenhum falso positivo. Sem ver a amostra
            antes de salvar, os dois parecem igualmente certos. */}
        <div className="mt-6 rounded-xl border border-neutral-200 bg-neutral-50 p-4">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="text-sm font-medium text-neutral-900">
              Marcaria <strong>{num(depois)}</strong> de {num(previa?.total_na_lista ?? 0)} peças
            </span>
            <span className="text-xs text-neutral-500">hoje: {num(hoje)}</span>
            {sujo && delta !== 0 && (
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                  delta > 0 ? "bg-blue-100 text-blue-800" : "bg-amber-100 text-amber-900"
                }`}
              >
                {delta > 0 ? `+${num(delta)} marcadas` : `${num(-delta)} deixam de exigir serial`}
              </span>
            )}
          </div>

          {previa && previa.exemplos.length > 0 && (
            <>
              <p className="mt-3 text-xs font-medium text-neutral-500">
                Amostra do que seria marcado — confira se não entrou acessório:
              </p>
              <ul className="mt-1.5 grid gap-x-6 gap-y-0.5 font-mono text-xs text-neutral-700 sm:grid-cols-2">
                {previa.exemplos.map((e) => (
                  <li key={e.part_number}>
                    <span className="text-neutral-400">{e.part_number}</span> {e.name}
                  </li>
                ))}
              </ul>
            </>
          )}
          {previa && previa.marcadas === 0 && (
            <p className="mt-3 text-xs text-neutral-500">
              Nenhuma peça seria marcada. Nenhum item vai pedir serial number.
            </p>
          )}
        </div>

        <div className="mt-5 flex items-center gap-3">
          <button
            onClick={() => salvar.mutate()}
            disabled={!sujo || salvar.isPending}
            className="cursor-pointer rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {salvar.isPending ? "Salvando…" : "Salvar e aplicar"}
          </button>
          {sujo && (
            <button
              onClick={() => {
                setSubstrings(regras.data?.substrings ?? []);
                setManuais(regras.data?.manual_part_numbers ?? []);
              }}
              className="cursor-pointer text-sm text-neutral-500 hover:text-neutral-900"
            >
              Descartar
            </button>
          )}
          {!sujo && regras.data && (
            <span className="text-xs text-neutral-400">
              Salvo em {new Date(regras.data.updated_at).toLocaleString("pt-BR")}
            </span>
          )}
        </div>
      </section>
    </main>
  );
}
