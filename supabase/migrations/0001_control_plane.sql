-- Ai-Personalization_Kernel: canonical control-plane schema (spec section 14)
-- Apply with: psql $DATABASE_URL -f supabase/migrations/0001_control_plane.sql
-- or paste into the Supabase SQL editor. Idempotent: safe to re-run.
--
-- Design invariants:
--  * every ledger table carries content_hash for idempotent write-through;
--  * provenance arrays (source_refs, supersedes, superseded_by) are jsonb,
--    never flattened away;
--  * updated_at is maintained by trigger, never trusted from the client;
--  * RLS is enabled with no public policies: reads/writes go through the
--    service role (which bypasses RLS) or policies you add explicitly.

begin;

create schema if not exists apk;

-- ---------------------------------------------------------------------------
-- updated_at trigger function, shared by all ledger tables
-- ---------------------------------------------------------------------------
create or replace function apk.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- Core ledger tables (MemoryObject envelope projections)
-- ---------------------------------------------------------------------------
create table if not exists apk.preferences (
  id            text primary key,
  type          text not null,
  scope         text not null check (scope in ('global','project','domain','conversation')),
  status        text not null check (status in ('active','superseded','resolved','quarantined')),
  confidence    double precision not null check (confidence between 0 and 1),
  source        text not null,
  source_refs   jsonb not null default '[]'::jsonb,
  payload       jsonb not null,
  content_hash  text not null,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  valid_from    timestamptz,
  valid_until   timestamptz,
  supersedes    jsonb not null default '[]'::jsonb,
  superseded_by jsonb not null default '[]'::jsonb,
  related_to    jsonb not null default '[]'::jsonb
);

create table if not exists apk.behavior_patterns (
  id            text primary key,
  type          text not null check (type in ('successful_strategy','failed_strategy','failure_pattern')),
  scope         text not null check (scope in ('global','project','domain','conversation')),
  status        text not null check (status in ('active','superseded','resolved','quarantined')),
  confidence    double precision not null check (confidence between 0 and 1),
  source        text not null,
  source_refs   jsonb not null default '[]'::jsonb,
  payload       jsonb not null,
  content_hash  text not null,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  valid_from    timestamptz,
  valid_until   timestamptz,
  supersedes    jsonb not null default '[]'::jsonb,
  superseded_by jsonb not null default '[]'::jsonb,
  related_to    jsonb not null default '[]'::jsonb
);

create table if not exists apk.policy_rules (
  id            text primary key,
  type          text not null,
  scope         text not null check (scope in ('global','project','domain','conversation')),
  status        text not null check (status in ('active','superseded','resolved','quarantined')),
  confidence    double precision not null check (confidence between 0 and 1),
  source        text not null,
  source_refs   jsonb not null default '[]'::jsonb,
  payload       jsonb not null,
  content_hash  text not null,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  valid_from    timestamptz,
  valid_until   timestamptz,
  supersedes    jsonb not null default '[]'::jsonb,
  superseded_by jsonb not null default '[]'::jsonb,
  related_to    jsonb not null default '[]'::jsonb
);

-- ---------------------------------------------------------------------------
-- Correction ledger (spec section 8.1 record shape)
-- ---------------------------------------------------------------------------
create table if not exists apk.corrections (
  id                 text primary key,
  type               text not null,
  pattern            text not null,
  scope              text not null check (scope in ('global','project','domain','conversation')),
  status             text not null check (status in ('active','superseded','resolved','quarantined')),
  desired_behavior   text not null,
  undesired_behavior text not null,
  confidence         double precision not null check (confidence between 0 and 1),
  recurrence_count   integer not null check (recurrence_count >= 1),
  promotion_level    text not null check (promotion_level in
                       ('observation','preference','strong_preference','procedural_rule','invariant')),
  first_seen         timestamptz not null,
  last_seen          timestamptz not null,
  source_refs        jsonb not null default '[]'::jsonb,
  supersedes         jsonb not null default '[]'::jsonb,
  superseded_by      jsonb not null default '[]'::jsonb,
  related_patterns   jsonb not null default '[]'::jsonb,
  content_hash       text not null,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Regression corpus (spec section 11)
-- ---------------------------------------------------------------------------
create table if not exists apk.regression_cases (
  id                     text primary key,
  failure_class          text not null,
  state                  jsonb not null,
  action_taken           text not null,
  user_correction        text not null,
  corrected_action       text not null,
  expected_policy_change text not null,
  source_refs            jsonb not null default '[]'::jsonb,
  content_hash           text not null,
  created_at             timestamptz not null default now(),
  updated_at             timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- User model (spec section 4): one node per top-level section
-- ---------------------------------------------------------------------------
create table if not exists apk.user_model_nodes (
  id           text primary key,          -- e.g. 'user_model/epistemic_preferences'
  section      text not null,
  payload      jsonb not null,
  content_hash text not null,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

create table if not exists apk.user_model_edges (
  id          bigint generated always as identity primary key,
  src_node    text not null references apk.user_model_nodes(id) on delete cascade,
  dst_node    text not null references apk.user_model_nodes(id) on delete cascade,
  edge_type   text not null,
  payload     jsonb not null default '{}'::jsonb,
  created_at  timestamptz not null default now(),
  unique (src_node, dst_node, edge_type)
);

-- ---------------------------------------------------------------------------
-- Remaining spec section 14 tables (schema-forward; Phase E fills them)
-- ---------------------------------------------------------------------------
create table if not exists apk.policy_events (
  id          bigint generated always as identity primary key,
  event_type  text not null,
  action      text,
  score       double precision,
  context     jsonb not null default '{}'::jsonb,
  created_at  timestamptz not null default now()
);

create table if not exists apk.project_states (
  id           text primary key,
  project      text not null,
  payload      jsonb not null,
  content_hash text not null,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

create table if not exists apk.memory_sources (
  id           text primary key,
  kind         text not null,             -- chat | file | app | web | provider
  uri          text not null,
  payload      jsonb not null default '{}'::jsonb,
  content_hash text not null,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

create table if not exists apk.source_claims (
  id           text primary key,
  source_id    text references apk.memory_sources(id) on delete set null,
  claim_type   text not null,             -- spec section 5.2 claim types
  claim        text not null,
  confidence   double precision not null check (confidence between 0 and 1),
  content_hash text not null,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

create table if not exists apk.resolutions (
  id           text primary key,
  subject_id   text not null,             -- record this resolution settles
  payload      jsonb not null,
  content_hash text not null,
  created_at   timestamptz not null default now()
);

create table if not exists apk.eval_runs (
  id           text primary key,
  metrics      jsonb not null,
  passed       boolean not null,
  content_hash text not null,
  created_at   timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Indexes: policy-consumption paths first
-- ---------------------------------------------------------------------------
create index if not exists preferences_type_status_idx    on apk.preferences (type, status);
create index if not exists preferences_content_hash_idx   on apk.preferences (content_hash);
create index if not exists behavior_patterns_type_idx     on apk.behavior_patterns (type, status);
create index if not exists policy_rules_type_idx          on apk.policy_rules (type, status);
create index if not exists corrections_pattern_idx        on apk.corrections (pattern, status);
create index if not exists corrections_content_hash_idx   on apk.corrections (content_hash);
create index if not exists regression_cases_class_idx     on apk.regression_cases (failure_class);
create index if not exists policy_events_created_idx      on apk.policy_events (created_at desc);

-- ---------------------------------------------------------------------------
-- updated_at triggers
-- ---------------------------------------------------------------------------
do $$
declare
  t text;
begin
  foreach t in array array[
    'preferences','behavior_patterns','policy_rules','corrections',
    'regression_cases','user_model_nodes','project_states',
    'memory_sources','source_claims'
  ]
  loop
    execute format(
      'drop trigger if exists set_updated_at on apk.%I;
       create trigger set_updated_at before update on apk.%I
       for each row execute function apk.set_updated_at();',
      t, t
    );
  end loop;
end $$;

-- ---------------------------------------------------------------------------
-- Row Level Security: locked by default. The service role bypasses RLS; add
-- explicit policies for any anon/authenticated access.
-- ---------------------------------------------------------------------------
do $$
declare
  t text;
begin
  foreach t in array array[
    'preferences','behavior_patterns','policy_rules','corrections',
    'regression_cases','user_model_nodes','user_model_edges','policy_events',
    'project_states','memory_sources','source_claims','resolutions','eval_runs'
  ]
  loop
    execute format('alter table apk.%I enable row level security;', t);
  end loop;
end $$;


-- ---------------------------------------------------------------------------
-- Grants: the service role (used by the connector) needs schema + table
-- privileges. anon/authenticated get nothing until you add RLS policies.
-- ---------------------------------------------------------------------------
grant usage on schema apk to service_role;
grant select, insert, update, delete on all tables in schema apk to service_role;
alter default privileges in schema apk
  grant select, insert, update, delete on tables to service_role;

commit;

-- ---------------------------------------------------------------------------
-- Post-migration step (cannot be done in SQL here): expose the schema to
-- PostgREST. In Supabase: Dashboard -> Project Settings -> API ->
-- "Exposed schemas" -> add `apk`. The connector sends Accept-Profile /
-- Content-Profile headers so `public` remains the default for other clients.
-- ---------------------------------------------------------------------------
