import { type ReactNode, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import {
  approveDocument,
  fileUrl,
  getDocument,
  rejectDocument,
  updateDocument,
} from "../api/documents";
import type { DocumentDetail as Detail, DocumentUpdate } from "../types/document";
import { StatusBadge } from "../components/StatusBadge";
import { canReview, isPending } from "../lib/status";
import { EMPTY, money } from "../lib/format";

const inputCls =
  "w-full rounded-lg border border-neutral-300 bg-white px-2 py-1 text-xs text-neutral-800 focus:border-neutral-900 focus:outline-none focus:ring-1 focus:ring-neutral-900";

interface LineForm {
  part_number: string;
  description: string;
  quantity: string;
  unit_price: string;
  amount: string;
  purchase_order: string;
  incoterm: string;
  country_of_origin: string;
  domestic_freight: string;
  packaging: string;
  exporter: string;
  supplier: string;
  manufacturer: string;
}

interface InvoiceForm {
  invoice_number: string;
  invoice_date: string;
  currency: string;
  total: string;
  line_items: LineForm[];
}

const str = (v: unknown): string => (v == null ? "" : String(v));

function buildForm(d: Detail): InvoiceForm[] {
  return d.invoices.map((inv) => ({
    invoice_number: str(inv.invoice_number),
    invoice_date: str(inv.invoice_date),
    currency: str(inv.currency),
    total: str(https://urldefense.com/v3/__http://inv.total__;!!FtR4BK4x7WL3xYs!7eSSCyFCjijlvTkq-nDu909aQ9KdSXixKzvq48ylXTbbOengh8CYIN7SlKKLdmZHwzuwWFqZehJczonqPhk0$ ),
    line_items: inv.line_items.map((li) => ({
      part_number: str(li.part_number),
      description: str(li.description),
      quantity: str(li.quantity),
      unit_price: str(li.unit_price),
      amount: str(li.amount),
      purchase_order: str(li.purchase_order),
      incoterm: str(li.incoterm),
      country_of_origin: str(li.country_of_origin),
      domestic_freight: str(li.domestic_freight),
      packaging: str(li.packaging),
      exporter: str(li.exporter),
      supplier: str(li.supplier),
      manufacturer: str(li.manufacturer),
    })),
  }));
}

function toPayload(invoices: InvoiceForm[]): DocumentUpdate {
  const orNull = (s: string) => (s.trim() === "" ? null : s.trim());
  return {
    invoices: invoices.map((inv) => ({
      invoice_number: orNull(inv.invoice_number),
      invoice_date: orNull(inv.invoice_date),
      currency: orNull(inv.currency),
      total: orNull(https://urldefense.com/v3/__http://inv.total__;!!FtR4BK4x7WL3xYs!7eSSCyFCjijlvTkq-nDu909aQ9KdSXixKzvq48ylXTbbOengh8CYIN7SlKKLdmZHwzuwWFqZehJczonqPhk0$ ),
      line_items: inv.line_items.map((l) => ({
        part_number: orNull(l.part_number),
        description: orNull(l.description),
        quantity: orNull(l.quantity),
        unit_price: orNull(l.unit_price),
        amount: orNull(l.amount),
        purchase_order: orNull(l.purchase_order),
        incoterm: orNull(l.incoterm),
        country_of_origin: orNull(l.country_of_origin),
        domestic_freight: orNull(l.domestic_freight),
        packaging: orNull(l.packaging),
        exporter: orNull(l.exporter),
        supplier: orNull(l.supplier),
        manufacturer: orNull(l.manufacturer),
      })),
    })),
  };
}

const emptyLine = (): LineForm => ({
  part_number: "",
  description: "",
  quantity: "",
  unit_price: "",
  amount: "",
  purchase_order: "",
  incoterm: "",
  country_of_origin: "",
  domestic_freight: "",
  packaging: "",
  exporter: "",
  supplier: "",
  manufacturer: "",
});

export function DocumentDetail() {
  const { id = "" } = useParams();
  const qc = useQueryClient();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["document", id],
    queryFn: () => getDocument(id),
    refetchInterval: (query) => {
      const d = https://urldefense.com/v3/__http://query.state.data__;!!FtR4BK4x7WL3xYs!7eSSCyFCjijlvTkq-nDu909aQ9KdSXixKzvq48ylXTbbOengh8CYIN7SlKKLdmZHwzuwWFqZehJczn4kielF$  as Detail | undefined;
      return d && isPending(d.status) ? 3000 : false;
    },
  });

  const editable = data ? canReview(data.status) : false;
  const [form, setForm] = useState<InvoiceForm[] | null>(null);
  const [baseline, setBaseline] = useState("");

  useEffect(() => {
    if (!data) return;
    const f = buildForm(data);
    setForm(f);
    setBaseline(JSON.stringify(f));
  }, [data?.id, data?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  const dirty = form != null && JSON.stringify(form) !== baseline;

  function invalidateAll() {
    qc.invalidateQueries({ queryKey: ["document", id] });
    qc.invalidateQueries({ queryKey: ["documents"] });
    qc.invalidateQueries({ queryKey: ["metrics"] });
  }

  const save = useMutation({
    mutationFn: () => updateDocument(id, toPayload(form!)),
    onSuccess: () => {
      if (form) setBaseline(JSON.stringify(form));
      invalidateAll();
    },
  });
  const approve = useMutation({ mutationFn: () => approveDocument(id), onSuccess: invalidateAll });
  const reject = useMutation({ mutationFn: () => rejectDocument(id), onSuccess: invalidateAll });

  async function onApprove() {
    if (editable && dirty) await save.mutateAsync();
    await approve.mutateAsync();
  }
  const busy = save.isPending || approve.isPending || reject.isPending;

  function setInv(i: number, k: keyof Omit<InvoiceForm, "line_items">, v: string) {
    setForm((f) => (f ? f.map((inv, j) => (j === i ? { ...inv, [k]: v } : inv)) : f));
  }
  // Aplica um valor a TODAS as linhas do invoice. Usado para Fornecedor e
  // Exportador, que sÃ£o por linha no modelo mas o usuÃ¡rio edita uma vez por invoice.
  function setAllLines(i: number, k: keyof LineForm, v: string) {
    setForm((f) =>
      f
        ? f.map((inv, j) =>
            j === i ? { ...inv, line_items: inv.line_items.map((l) => ({ ...l, [k]: v })) } : inv
          )
        : f
    );
  }
  function setLine(i: number, li: number, k: keyof LineForm, v: string) {
    setForm((f) =>
      f
        ? f.map((inv, j) =>
            j === i
              ? { ...inv, line_items: inv.line_items.map((l, m) => (m === li ? { ...l, [k]: v } : l)) }
              : inv
          )
        : f
    );
  }
  function addLine(i: number) {
    setForm((f) =>
      f ? f.map((inv, j) => (j === i ? { ...inv, line_items: [...inv.line_items, emptyLine()] } : inv)) : f
    );
  }
  function removeLine(i: number, li: number) {
    setForm((f) =>
      f
        ? f.map((inv, j) =>
            j === i ? { ...inv, line_items: inv.line_items.filter((_, m) => m !== li) } : inv
          )
        : f
    );
  }
  function removeInvoice(i: number) {
    setForm((f) => (f ? f.filter((_, j) => j !== i) : f));
  }
  function addInvoice() {
    setForm((f) =>
      f ? [...f, { invoice_number: "", invoice_date: "", currency: "", total: "", line_items: [emptyLine()] }] : f
    );
  }

  return (
    <div className="flex h-[calc(100vh-49px)] flex-col">
      <header className="flex items-center border-b border-neutral-200 bg-white px-6 py-2.5">
        <Link to="/" className="flex items-center gap-1 text-sm font-medium text-neutral-600 hover:text-neutral-900">
          â† Voltar
        </Link>
        <div className="ml-auto flex items-center gap-2 text-sm text-neutral-500">
          {data && (
            <>
              Status: <StatusBadge status={data.status} />
            </>
          )}
        </div>
      </header>

      {isLoading && <p className="p-8 text-neutral-400">Carregandoâ€¦</p>}
      {isError && <p className="p-8 text-red-600">Falha ao carregar o documento.</p>}

      {data && form && (
        <div className="grid flex-1 grid-cols-1 overflow-hidden lg:grid-cols-2">
          {/* PDF */}
          <div className="border-r border-neutral-200 bg-neutral-100 p-4">
            <iframe
              title="documento-pdf"
              src={fileUrl(https://urldefense.com/v3/__http://data.id__;!!FtR4BK4x7WL3xYs!7eSSCyFCjijlvTkq-nDu909aQ9KdSXixKzvq48ylXTbbOengh8CYIN7SlKKLdmZHwzuwWFqZehJczjLQK3RG$ )}
              className="h-full w-full rounded-lg border border-neutral-200 bg-white"
            />
          </div>

          {/* Dados extraÃ­dos */}
          <div className="overflow-auto p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h1 className="text-lg font-semibold text-neutral-900">
                  {data.source_filename || "Documento"}
                </h1>
                <p className="mt-0.5 text-xs text-neutral-400">
                  {data.invoices.length} invoice(s)
                  {data.extraction_confidence != null && (
                    <> Â· confianÃ§a {(data.extraction_confidence * 100).toFixed(0)}%</>
                  )}
                </p>
              </div>
              {editable && (
                <span className="shrink-0 rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700 ring-1 ring-inset ring-blue-600/20">
                  Em revisÃ£o
                </span>
              )}
            </div>

            {data.status === "error" && data.error_message && (
              <div className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{data.error_message}</div>
            )}

            <div className="mt-5 space-y-5">
              {form.map((inv, i) => (
                <div key={i} className="rounded-xl border border-neutral-200 bg-white p-4">
                  <div className="mb-3 flex items-start justify-between gap-3">
                    <div className="grid flex-1 grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3">
                      {editable ? (
                        <>
                          <FieldInput label="NÂº invoice" value={inv.invoice_number} onChange={(v) => setInv(i, "invoice_number", v)} />
                          <FieldInput label="Data" type="date" value={inv.invoice_date} onChange={(v) => setInv(i, "invoice_date", v)} />
                          <FieldInput label="Moeda" value={inv.currency} onChange={(v) => setInv(i, "currency", v)} />
                          <FieldInput label="Total" value={https://urldefense.com/v3/__http://inv.total__;!!FtR4BK4x7WL3xYs!7eSSCyFCjijlvTkq-nDu909aQ9KdSXixKzvq48ylXTbbOengh8CYIN7SlKKLdmZHwzuwWFqZehJczonqPhk0$ } onChange={(v) => setInv(i, "total", v)} />
                          <FieldInput label="Fornecedor" value={inv.line_items[0]?.supplier ?? ""} onChange={(v) => setAllLines(i, "supplier", v)} />
                          <FieldInput label="Exportador" value={inv.line_items[0]?.exporter ?? ""} onChange={(v) => setAllLines(i, "exporter", v)} />
                        </>
                      ) : (
                        <>
                          <ReadField label="NÂº invoice" value={data.invoices[i]?.invoice_number} />
                          <ReadField label="Data" value={data.invoices[i]?.invoice_date} />
                          <ReadField label="Moeda" value={data.invoices[i]?.currency} />
                          <ReadField label="Total" value={money(data.invoices[i]?.total ?? null, data.invoices[i]?.currency ?? null)} />
                          <ReadField label="Fornecedor" value={inv.line_items[0]?.supplier} />
                          <ReadField label="Exportador" value={inv.line_items[0]?.exporter} />
                        </>
                      )}
                    </div>
                    {editable && (
                      <button
                        onClick={() => removeInvoice(i)}
                        className="shrink-0 text-xs text-neutral-400 hover:text-red-600"
                        title="Remover invoice"
                      >
                        Remover
                      </button>
                    )}
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="text-[11px] uppercase tracking-wide text-neutral-400">
                        <tr>
                          <th className="py-1.5 pr-2 font-medium">Part #</th>
                          <th className="py-1.5 pr-2 font-medium">DescriÃ§Ã£o</th>
                          <th className="py-1.5 pr-2 text-right font-medium">Qtd</th>
                          <th className="py-1.5 pr-2 text-right font-medium">UnitÃ¡rio{inv.currency ? ` (${inv.currency})` : ""}</th>
                          <th className="py-1.5 pr-2 text-right font-medium">Total{inv.currency ? ` (${inv.currency})` : ""}</th>
                          <th className="py-1.5 pr-2 font-medium">PO</th>
                          <th className="py-1.5 pr-2 font-medium">Incoterm</th>
                          <th className="py-1.5 pr-2 font-medium">Origem</th>
                          <th className="py-1.5 pr-2 font-medium">Fabricante</th>
                          <th className="py-1.5 pr-2 text-right font-medium">Frete{inv.currency ? ` (${inv.currency})` : ""}</th>
                          <th className="py-1.5 pr-2 font-medium">Embalagem</th>
                          {editable && <th className="py-1.5" />}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-neutral-100 align-top">
                        {inv.line_items.map((l, li) => (
                          <tr key={li}>
                            {editable ? (
                              <>
                                <Cell><input className={inputCls} value={l.part_number} onChange={(e) => setLine(i, li, "part_number", e.target.value)} /></Cell>
                                <Cell wide><input className={inputCls} value={l.description} onChange={(e) => setLine(i, li, "description", e.target.value)} /></Cell>
                                <Cell><input className={inputCls} inputMode="decimal" value={l.quantity} onChange={(e) => setLine(i, li, "quantity", e.target.value)} /></Cell>
                                <Cell><input className={inputCls} inputMode="decimal" value={l.unit_price} onChange={(e) => setLine(i, li, "unit_price", e.target.value)} /></Cell>
                                <Cell><input className={inputCls} inputMode="decimal" value={l.amount} onChange={(e) => setLine(i, li, "amount", e.target.value)} /></Cell>
                                <Cell><input className={inputCls} value={l.purchase_order} onChange={(e) => setLine(i, li, "purchase_order", e.target.value)} /></Cell>
                                <Cell><input className={inputCls} value={l.incoterm} onChange={(e) => setLine(i, li, "incoterm", e.target.value)} /></Cell>
                                <Cell><input className={inputCls} value={l.country_of_origin} onChange={(e) => setLine(i, li, "country_of_origin", e.target.value)} /></Cell>
                                <Cell><input className={inputCls} value={l.manufacturer} onChange={(e) => setLine(i, li, "manufacturer", e.target.value)} /></Cell>
                                <Cell><input className={inputCls} inputMode="decimal" value={l.domestic_freight} onChange={(e) => setLine(i, li, "domestic_freight", e.target.value)} /></Cell>
                                <Cell wide><input className={inputCls} value={l.packaging} onChange={(e) => setLine(i, li, "packaging", e.target.value)} placeholder="ex.: EUROPALLET 1200x800x345 mm" /></Cell>
                                <td className="py-1 pl-1 text-center">
                                  <button onClick={() => removeLine(i, li)} className="text-neutral-300 hover:text-red-600" title="Remover linha">âœ•</button>
                                </td>
                              </>
                            ) : (
                              <>
                                <td className="py-1.5 pr-2 font-mono text-neutral-700">{l.part_number || EMPTY}</td>
                                <td className="py-1.5 pr-2 text-neutral-800">{l.description || EMPTY}</td>
                                <td className="py-1.5 pr-2 text-right tabular text-neutral-600">{l.quantity || EMPTY}</td>
                                <td className="py-1.5 pr-2 text-right tabular text-neutral-600">{money(l.unit_price || null, inv.currency || null)}</td>
                                <td className="py-1.5 pr-2 text-right tabular text-neutral-700">{money(l.amount || null, inv.currency || null)}</td>
                                <td className="py-1.5 pr-2 font-mono text-neutral-500">{l.purchase_order || EMPTY}</td>
                                <td className="py-1.5 pr-2 text-neutral-500">{l.incoterm || EMPTY}</td>
                                <td className="py-1.5 pr-2 text-neutral-500">{l.country_of_origin || EMPTY}</td>
                                <td className="py-1.5 pr-2 text-neutral-500">{l.manufacturer || EMPTY}</td>
                                <td className="py-1.5 pr-2 text-right tabular text-neutral-500">{money(l.domestic_freight || null, inv.currency || null)}</td>
                                <td className="py-1.5 pr-2 text-neutral-500">{l.packaging || EMPTY}</td>
                              </>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {editable && (
                    <button onClick={() => addLine(i)} className="mt-2 cursor-pointer text-xs font-medium text-neutral-600 hover:text-neutral-900">
                      + Adicionar linha
                    </button>
                  )}
                </div>
              ))}

              {editable && (
                <button
                  onClick={addInvoice}
                  className="w-full cursor-pointer rounded-xl border border-dashed border-neutral-300 py-2 text-sm font-medium text-neutral-500 hover:border-neutral-400 hover:text-neutral-700"
                >
                  + Adicionar invoice
                </button>
              )}
            </div>

            {/* AÃ§Ãµes */}
            <div className="mt-6 flex flex-wrap items-center gap-3">
              {editable ? (
                <>
                  <button
                    disabled={!dirty || busy}
                    onClick={() => save.mutate()}
                    className="cursor-pointer rounded-lg border border-neutral-300 bg-white px-4 py-2 text-sm font-medium text-neutral-700 transition-colors hover:bg-neutral-50 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {save.isPending ? "Salvandoâ€¦" : "Salvar alteraÃ§Ãµes"}
                  </button>
                  <button
                    disabled={busy}
                    onClick={onApprove}
                    className="cursor-pointer rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:opacity-40"
                  >
                    {approve.isPending ? "Aprovandoâ€¦" : "Aprovar documento"}
                  </button>
                  <button
                    disabled={busy}
                    onClick={() => reject.mutate()}
                    className="cursor-pointer rounded-lg border border-red-200 bg-white px-4 py-2 text-sm font-medium text-red-600 transition-colors hover:bg-red-50 disabled:opacity-40"
                  >
                    {reject.isPending ? "â€¦" : "Rejeitar"}
                  </button>
                  {dirty && !busy && <span className="text-xs text-amber-600">HÃ¡ alteraÃ§Ãµes nÃ£o salvas</span>}
                </>
              ) : data.status === "approved" ? (
                <span className="inline-flex items-center gap-2 text-sm font-medium text-emerald-700">
                  âœ“ Documento aprovado (somente leitura)
                </span>
              ) : data.status === "rejected" ? (
                <span className="text-sm font-medium text-red-600">Documento rejeitado</span>
              ) : null}
              {(save.isError || approve.isError || reject.isError) && (
                <span className="text-sm text-red-600">
                  {((save.error || approve.error || reject.error) as Error)?.message}
                </span>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// --- pequenos componentes de apresentaÃ§Ã£o ---

function FieldInput({
  label,
  value,
  onChange,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
}) {
  return (
    <label className="block">
      <span className="text-[11px] uppercase tracking-wide text-neutral-400">{label}</span>
      <input type={type} value={value} onChange={(e) => onChange(e.target.value)} className={`mt-0.5 ${inputCls}`} />
    </label>
  );
}

function ReadField({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wide text-neutral-400">{label}</dt>
      <dd className="mt-0.5 text-sm font-medium text-neutral-800">{value == null || value === "" ? EMPTY : value}</dd>
    </div>
  );
}

function Cell({ children, wide }: { children: ReactNode; wide?: boolean }) {
  return <td className={`py-1 pr-1.5 ${wide ? "min-w-[150px]" : "min-w-[72px]"}`}>{children}</td>;
}
