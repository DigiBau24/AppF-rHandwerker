-- =====================================================================
-- Job-Costing / Nachkalkulation für Handwerksbetriebe
-- PostgreSQL-Schema für Supabase
-- =====================================================================
-- Designprinzipien:
--  1. Mandantenfähigkeit: JEDE Fachtabelle trägt company_id.
--  2. Mandanten-Integrität auf DB-Ebene: Kinder-Tabellen referenzieren
--     (projekt_id, company_id) per Composite-FK -> ein Zeitbuchung kann
--     NIE einem Projekt einer anderen Firma zugeordnet werden, auch
--     nicht durch einen Bug im Backend.
--  3. Geld = numeric(12,2), niemals float (Rundungsfehler).
--  4. Row Level Security als zweite Verteidigungslinie (z. B. wenn das
--     Next.js-Frontend später direkt per supabase-js zugreift).
--  5. Kein ON DELETE CASCADE auf Kostendaten: Buchhaltungsdaten sollen
--     nicht versehentlich verschwinden -> Projekte werden archiviert.
-- =====================================================================

create extension if not exists pgcrypto;

create type public.project_status as enum ('geplant', 'aktiv', 'abgeschlossen', 'archiviert');
create type public.user_role      as enum ('owner', 'admin', 'member');

-- Generischer Trigger für updated_at
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

-- ---------------------------------------------------------------------
-- companies (Mandanten)
-- ---------------------------------------------------------------------
create table public.companies (
  id         uuid primary key default gen_random_uuid(),
  name       text not null check (length(btrim(name)) > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create trigger trg_companies_updated before update on public.companies
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------
-- users (Profil-Tabelle, 1:1 zu auth.users von Supabase Auth)
-- Passwörter/Login liegen bewusst NICHT hier, sondern in auth.users.
-- ---------------------------------------------------------------------
create table public.users (
  id         uuid primary key references auth.users (id) on delete cascade,
  company_id uuid not null references public.companies (id) on delete restrict,
  email      text,
  full_name  text,
  role       public.user_role not null default 'member',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index idx_users_company on public.users (company_id);
create trigger trg_users_updated before update on public.users
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------
-- projects
-- ---------------------------------------------------------------------
create table public.projects (
  id           uuid primary key default gen_random_uuid(),
  company_id   uuid not null references public.companies (id) on delete restrict,
  projekt_name text not null check (length(btrim(projekt_name)) > 0),
  budget_netto numeric(12,2) not null check (budget_netto >= 0),
  status       public.project_status not null default 'aktiv',
  start_datum  date not null default current_date,
  created_by   uuid references public.users (id) on delete set null,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  -- Ziel für die Composite-FKs der Kinder-Tabellen (siehe Designprinzip 2)
  constraint projects_id_company_uniq unique (id, company_id)
);
-- Gleicher Projektname nur einmal pro Firma (Groß/Kleinschreibung egal)
create unique index uq_projects_company_name on public.projects (company_id, lower(projekt_name));
create index idx_projects_company_status on public.projects (company_id, status);
create trigger trg_projects_updated before update on public.projects
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------
-- material_costs (Eingangsrechnungen, z. B. per Gemini-OCR erfasst)
-- betrag_netto darf negativ sein -> Gutschriften der Großhändler.
-- gemini_raw_json: Roh-Antwort der KI für Nachvollziehbarkeit/Reparsing.
-- ---------------------------------------------------------------------
create table public.material_costs (
  id              uuid primary key default gen_random_uuid(),
  company_id      uuid not null,
  projekt_id      uuid not null,
  rechnungs_datum date not null,
  grosshaendler   text not null check (length(btrim(grosshaendler)) > 0),
  betrag_netto    numeric(12,2) not null,
  gemini_raw_json jsonb,
  created_by      uuid references public.users (id) on delete set null,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  constraint material_costs_projekt_fk
    foreign key (projekt_id, company_id)
    references public.projects (id, company_id) on delete restrict
);
create index idx_material_costs_projekt on public.material_costs (company_id, projekt_id, rechnungs_datum);
create trigger trg_material_costs_updated before update on public.material_costs
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------
-- work_hours
-- stundensatz_intern wird pro Buchung "eingefroren": spätere Lohn-
-- erhöhungen verfälschen so keine bereits abgeschlossene Nachkalkulation.
-- ---------------------------------------------------------------------
create table public.work_hours (
  id                 uuid primary key default gen_random_uuid(),
  company_id         uuid not null,
  projekt_id         uuid not null,
  datum              date not null,
  mitarbeiter_name   text not null check (length(btrim(mitarbeiter_name)) > 0),
  stunden_anzahl     numeric(5,2) not null check (stunden_anzahl > 0 and stunden_anzahl <= 24),
  stundensatz_intern numeric(8,2) not null check (stundensatz_intern >= 0),
  created_by         uuid references public.users (id) on delete set null,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now(),
  constraint work_hours_projekt_fk
    foreign key (projekt_id, company_id)
    references public.projects (id, company_id) on delete restrict
);
create index idx_work_hours_projekt on public.work_hours (company_id, projekt_id, datum);
create trigger trg_work_hours_updated before update on public.work_hours
  for each row execute function public.set_updated_at();

-- =====================================================================
-- Row Level Security
-- =====================================================================
-- SECURITY DEFINER, damit die Policy auf public.users keine Rekursion auslöst.
create or replace function public.current_company_id()
returns uuid
language sql stable security definer
set search_path = public
as $$
  select company_id from public.users where id = auth.uid()
$$;
revoke all on function public.current_company_id() from public, anon;
grant execute on function public.current_company_id() to authenticated;

alter table public.companies      enable row level security;
alter table public.users          enable row level security;
alter table public.projects       enable row level security;
alter table public.material_costs enable row level security;
alter table public.work_hours     enable row level security;

-- companies / users: nur lesen. Schreiben läuft über Backend bzw. onboard_company().
-- (Kein UPDATE auf users für Clients -> keine Rollen-Eskalation möglich.)
create policy companies_select on public.companies
  for select to authenticated using (id = public.current_company_id());
create policy users_select on public.users
  for select to authenticated using (company_id = public.current_company_id());

create policy projects_all on public.projects
  for all to authenticated
  using (company_id = public.current_company_id())
  with check (company_id = public.current_company_id());

create policy material_costs_all on public.material_costs
  for all to authenticated
  using (company_id = public.current_company_id())
  with check (company_id = public.current_company_id());

create policy work_hours_all on public.work_hours
  for all to authenticated
  using (company_id = public.current_company_id())
  with check (company_id = public.current_company_id());

-- =====================================================================
-- Onboarding: neue Firma + Owner-Profil für den eingeloggten Nutzer anlegen
-- (per supabase.rpc('onboard_company', {...}) direkt nach der Registrierung)
-- =====================================================================
create or replace function public.onboard_company(p_company_name text, p_full_name text default null)
returns uuid
language plpgsql security definer
set search_path = public
as $$
declare
  v_uid        uuid := auth.uid();
  v_company_id uuid;
  v_email      text;
begin
  if v_uid is null then
    raise exception 'Nicht authentifiziert' using errcode = '28000';
  end if;
  if p_company_name is null or length(btrim(p_company_name)) = 0 then
    raise exception 'Firmenname darf nicht leer sein' using errcode = '22023';
  end if;
  if exists (select 1 from public.users where id = v_uid) then
    raise exception 'Nutzer ist bereits einer Firma zugeordnet' using errcode = '23505';
  end if;

  select email into v_email from auth.users where id = v_uid;

  insert into public.companies (name) values (btrim(p_company_name))
  returning id into v_company_id;

  insert into public.users (id, company_id, email, full_name, role)
  values (v_uid, v_company_id, v_email, p_full_name, 'owner');

  return v_company_id;
end $$;
revoke all on function public.onboard_company(text, text) from public, anon;
grant execute on function public.onboard_company(text, text) to authenticated;
