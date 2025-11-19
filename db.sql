-- ============================
--  ANALYTICS TABLE
-- ============================
create table if not exists public.analytics (
  id uuid not null default gen_random_uuid(),
  event_type varchar(50) not null,
  timestamp timestamptz not null default now(),
  metadata jsonb null default '{}'::jsonb,
  user_agent text null,
  ip_address varchar(45) null,
  created_at timestamptz null default now(),
  constraint analytics_pkey primary key (id)
);

create index if not exists idx_analytics_event_type
  on public.analytics (event_type);

create index if not exists idx_analytics_timestamp
  on public.analytics ("timestamp" desc);

create index if not exists idx_analytics_event_timestamp
  on public.analytics (event_type, "timestamp" desc);


-- ============================
--  NOTIFICATIONS TABLE
-- ============================
create table if not exists public.notifications (
  id uuid not null default extensions.uuid_generate_v4(),
  title text not null,
  message text not null,
  created_at timestamptz null default now(),
  constraint notifications_pkey primary key (id)
);


-- ============================
--  SESSIONS TABLE
-- ============================
create table if not exists public.sessions (
  id uuid not null default gen_random_uuid(),
  token text not null,
  email text not null,
  issue text null,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '30 minutes'),
  active boolean not null default true,
  plan jsonb null,
  plan_type text null default 'basic',
  transaction_ref text null,
  constraint sessions_pkey primary key (id)
);

create index if not exists idx_sessions_plan_type
  on public.sessions (plan_type);


-- ============================
--  ANALYTICS SUMMARY TABLE
-- ============================
create table if not exists public.analytics_summary (
  date date not null,
  event_type varchar(50) not null,
  count bigint not null default 0,
  unique_users bigint not null default 0,
  constraint analytics_summary_pk primary key (date, event_type)
);
