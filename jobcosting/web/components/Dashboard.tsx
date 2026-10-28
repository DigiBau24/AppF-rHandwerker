"use client";
import { useCallback, useEffect, useState } from "react";
import BelegScan from "./BelegScan";
import ProjectDetail from "./ProjectDetail";
import { api, ApiError, Ampel, ProjectStatus, eur } from "@/lib/api";

const COLORS: Record<Ampel, string> = { green: "bg-green-500", yellow: "bg-yellow-400", red: "bg-red-500" };
const LABELS: Record<Ampel, string> = { green: "Im Budget", yellow: "Achtung ab 80 %", red: "Budget überschritten" };
const today = () => new Date().toISOString().slice(0, 10);

function HoursForm({ projektId, onDone }: { projektId: string; onDone: () => void }) {
  const [f, setF] = useState({ mitarbeiter_name: "", stunden_anzahl: "", stundensatz_intern: "", datum: today() });
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    try {
      await api("/api/v1/work-hours", { method: "POST", body: JSON.stringify({ ...f, projekt_id: projektId }) });
      setF({ ...f, stunden_anzahl: "" });
      onDone();
    } catch (e) {
      setErr((e as Error).message);
    }
  }
  const input = "w-full rounded-lg border p-3";
  return (
    <form onSubmit={submit} className="mt-3 grid grid-cols-2 gap-2">
      <input className={`${input} col-span-2`} placeholder="Mitarbeiter" required value={f.mitarbeiter_name}
        onChange={(e) => setF({ ...f, mitarbeiter_name: e.target.value })} />
      <input className={input} type="number" step="0.25" min="0.25" max="24" placeholder="Stunden" required
        value={f.stunden_anzahl} onChange={(e) => setF({ ...f, stunden_anzahl: e.target.value })} />
      <input className={input} type="number" step="0.01" min="0" placeholder="€/Std intern" required
        value={f.stundensatz_intern} onChange={(e) => setF({ ...f, stundensatz_intern: e.target.value })} />
      <input className={`${input} col-span-2`} type="date" required value={f.datum}
        onChange={(e) => setF({ ...f, datum: e.target.value })} />
      {err && <p className="col-span-2 text-sm text-red-600">{err}</p>}
      <button className="col-span-2 rounded-lg bg-slate-900 p-3 font-semibold text-white">Stunden buchen</button>
    </form>
  );
}

function ProjectCard({ p, onChange }: { p: ProjectStatus; onChange: () => void }) {
  const [open, setOpen] = useState(false);
  const [showEntries, setShowEntries] = useState(false);
  const pct = Math.min(Number(p.budget_verbrauch_prozent ?? 100), 100);
  return (
    <li className="rounded-2xl bg-white p-4 shadow">
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-semibold">{p.projekt_name}</h3>
        <span className="flex items-center gap-2 text-xs text-slate-600">
          <span className={`h-3 w-3 rounded-full ${COLORS[p.status_ampel]}`} />
          {LABELS[p.status_ampel]}
        </span>
      </div>
      <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-200">
        <div className={`h-full ${COLORS[p.status_ampel]}`} style={{ width: `${pct}%` }} />
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-1 text-sm">
        <dt className="text-slate-500">Budget</dt><dd className="text-right">{eur(p.budget_netto)}</dd>
        <dt className="text-slate-500">Material</dt><dd className="text-right">{eur(p.material_kosten)}</dd>
        <dt className="text-slate-500">Lohn</dt><dd className="text-right">{eur(p.lohnkosten)}</dd>
        <dt className="font-semibold">Rest</dt>
        <dd className={`text-right font-semibold ${Number(p.restbudget) < 0 ? "text-red-600" : ""}`}>{eur(p.restbudget)}</dd>
      </dl>
      <button className="mt-3 text-sm font-medium underline" onClick={() => setOpen(!open)}>
        {open ? "Schließen" : "Stunden buchen"}
      </button>
      {open && <HoursForm projektId={p.projekt_id} onDone={onChange} />}
      <button className="mt-3 ml-4 text-sm font-medium underline" onClick={() => setShowEntries(!showEntries)}>
        {showEntries ? "Buchungen ausblenden" : "Buchungen anzeigen"}
      </button>
      {showEntries && <ProjectDetail projektId={p.projekt_id} version={p.gesamtkosten} onChange={onChange} />}
    </li>
  );
}

export default function Dashboard({ onNoCompany }: { onNoCompany: () => void }) {
  const [projects, setProjects] = useState<ProjectStatus[] | null>(null);
  const [name, setName] = useState("");
  const [budget, setBudget] = useState("");
  const [scanOpen, setScanOpen] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setProjects(await api<ProjectStatus[]>("/api/v1/projects"));
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) onNoCompany();
      else setErr((e as Error).message);
    }
  }, [onNoCompany]);

  useEffect(() => { load(); }, [load]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    try {
      await api("/api/v1/projects", { method: "POST", body: JSON.stringify({ projekt_name: name, budget_netto: budget }) });
      setName(""); setBudget("");
      load();
    } catch (e) {
      setErr((e as Error).message);
    }
  }

  return (
    <div className="space-y-6">
      {scanOpen ? (
        <BelegScan projects={projects ?? []} onCancel={() => setScanOpen(false)} onDone={() => { setScanOpen(false); load(); }} />
      ) : (
        <button onClick={() => setScanOpen(true)} disabled={!projects?.length}
          className="min-h-14 w-full rounded-2xl bg-orange-500 text-base font-bold text-slate-900 disabled:opacity-40">
          Beleg fotografieren
        </button>
      )}
      <form onSubmit={create} className="space-y-2 rounded-2xl bg-white p-4 shadow">
        <h2 className="font-semibold">Neues Projekt</h2>
        <input className="w-full rounded-lg border p-3" placeholder="Projektname" required value={name}
          onChange={(e) => setName(e.target.value)} />
        <input className="w-full rounded-lg border p-3" type="number" step="0.01" min="0" placeholder="Budget netto (€)"
          required value={budget} onChange={(e) => setBudget(e.target.value)} />
        <button className="w-full rounded-lg bg-slate-900 p-3 font-semibold text-white">Projekt anlegen</button>
      </form>
      {err && <p className="text-sm text-red-600">{err}</p>}
      {projects === null ? <p className="text-slate-500">Lade …</p> : projects.length === 0 ? (
        <p className="text-slate-500">Noch keine Projekte.</p>
      ) : (
        <ul className="space-y-4">{projects.map((p) => <ProjectCard key={p.projekt_id} p={p} onChange={load} />)}</ul>
      )}
    </div>
  );
}
