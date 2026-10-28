"use client";
import { useCallback, useEffect, useState } from "react";
import { api, eur } from "@/lib/api";

interface Material { id: string; rechnungs_datum: string; grosshaendler: string; betrag_netto: string }
interface Hours { id: string; datum: string; mitarbeiter_name: string; stunden_anzahl: string; stundensatz_intern: string }
interface Entries { material: Material[]; hours: Hours[] }
type Kind = "material-costs" | "work-hours";

const FIELDS: Record<Kind, [string, string, string][]> = {
  "material-costs": [["grosshaendler", "Großhändler", "text"], ["rechnungs_datum", "Datum", "date"], ["betrag_netto", "Netto (€)", "number"]],
  "work-hours": [["mitarbeiter_name", "Mitarbeiter", "text"], ["datum", "Datum", "date"], ["stunden_anzahl", "Stunden", "number"], ["stundensatz_intern", "€/Std", "number"]],
};
const de = (iso: string) => new Date(iso + "T00:00:00").toLocaleDateString("de-DE");
const btn = "min-h-11 min-w-11 rounded-lg px-2 text-sm font-medium underline";

export default function ProjectDetail({ projektId, version, onChange }: {
  projektId: string; version: string; onChange: () => void;
}) {
  const [data, setData] = useState<Entries | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [edit, setEdit] = useState<{ kind: Kind; id: string } | null>(null);
  const [vals, setVals] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    try { setData(await api<Entries>(`/api/v1/projects/${projektId}/entries`)); }
    catch (e) { setErr((e as Error).message); }
  }, [projektId]);
  // version = Gesamtkosten: ändern sie sich, wird die Liste neu geladen
  useEffect(() => { load(); }, [load, version]);

  async function remove(kind: Kind, id: string) {
    if (!confirm("Diese Buchung wirklich löschen?")) return;
    setErr(null);
    try { await api(`/api/v1/${kind}/${id}`, { method: "DELETE" }); onChange(); }
    catch (e) { setErr((e as Error).message); }
  }
  async function saveEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!edit) return;
    setErr(null);
    try {
      await api(`/api/v1/${edit.kind}/${edit.id}`, { method: "PATCH", body: JSON.stringify(vals) });
      setEdit(null); onChange(); load();
    } catch (e) { setErr((e as Error).message); }
  }
  const startEdit = (kind: Kind, id: string, v: Record<string, string>) => { setEdit({ kind, id }); setVals(v); setErr(null); };

  function EditForm() {
    if (!edit) return null;
    return (
      <form onSubmit={saveEdit} className="grid grid-cols-2 gap-2 rounded-xl bg-slate-50 p-3">
        {FIELDS[edit.kind].map(([key, label, type]) => (
          <label key={key} className="text-xs font-semibold text-slate-600">
            {label}
            <input className="mt-1 min-h-11 w-full rounded-lg border border-slate-300 bg-white px-2 text-base font-normal text-slate-900"
              type={type} step={type === "number" ? "0.01" : undefined} required value={vals[key] ?? ""}
              onChange={(e) => setVals({ ...vals, [key]: e.target.value })} />
          </label>
        ))}
        <button className="min-h-11 rounded-lg bg-slate-900 font-semibold text-white">Speichern</button>
        <button type="button" className="min-h-11 rounded-lg border border-slate-300" onClick={() => setEdit(null)}>Abbrechen</button>
      </form>
    );
  }

  if (!data) return <p className="mt-3 text-sm text-slate-500">{err ?? "Lade …"}</p>;
  return (
    <div className="mt-3 space-y-4 border-t border-slate-200 pt-3 text-sm">
      {err && <p className="text-red-600">{err}</p>}
      <section>
        <h4 className="mb-1 font-semibold">Material ({data.material.length})</h4>
        {data.material.length === 0 && <p className="text-slate-500">Keine Belege.</p>}
        <ul className="divide-y divide-slate-100">
          {data.material.map((m) => (
            <li key={m.id} className="py-1">
              {edit?.id === m.id ? EditForm() : (
                <div className="flex items-center justify-between gap-1">
                  <span>{de(m.rechnungs_datum)} · {m.grosshaendler}<br /><b className="font-medium">{eur(m.betrag_netto)}</b></span>
                  <span className="flex shrink-0">
                    <button className={btn} onClick={() => startEdit("material-costs", m.id, { grosshaendler: m.grosshaendler, rechnungs_datum: m.rechnungs_datum, betrag_netto: m.betrag_netto })}>Ändern</button>
                    <button className={`${btn} text-red-700`} onClick={() => remove("material-costs", m.id)}>Löschen</button>
                  </span>
                </div>
              )}
            </li>
          ))}
        </ul>
      </section>
      <section>
        <h4 className="mb-1 font-semibold">Stunden ({data.hours.length})</h4>
        {data.hours.length === 0 && <p className="text-slate-500">Keine Stunden.</p>}
        <ul className="divide-y divide-slate-100">
          {data.hours.map((h) => (
            <li key={h.id} className="py-1">
              {edit?.id === h.id ? EditForm() : (
                <div className="flex items-center justify-between gap-1">
                  <span>{de(h.datum)} · {h.mitarbeiter_name}<br />
                    <b className="font-medium">{Number(h.stunden_anzahl)} Std × {eur(h.stundensatz_intern)} = {eur(Number(h.stunden_anzahl) * Number(h.stundensatz_intern))}</b></span>
                  <span className="flex shrink-0">
                    <button className={btn} onClick={() => startEdit("work-hours", h.id, { mitarbeiter_name: h.mitarbeiter_name, datum: h.datum, stunden_anzahl: h.stunden_anzahl, stundensatz_intern: h.stundensatz_intern })}>Ändern</button>
                    <button className={`${btn} text-red-700`} onClick={() => remove("work-hours", h.id)}>Löschen</button>
                  </span>
                </div>
              )}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
