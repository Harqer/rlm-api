-- Run this once in the Supabase SQL editor (or `supabase db push`) for your project.

create extension if not exists "uuid-ossp";

create table if not exists api_keys (
    id uuid primary key default uuid_generate_v4(),
    key_hash text not null unique,              -- sha256 of the raw key; raw key shown once at creation
    key_prefix text not null,                    -- first 12 chars, safe to display in dashboards/logs
    owner_label text not null,                    -- e.g. 'quix-spresso-prod', 'musically-studio-dev'
    tier text not null default 'byok',            -- 'byok' (bring your own LLM key) | 'managed'
    monthly_token_quota bigint,                   -- null = unlimited
    tokens_used_this_period bigint not null default 0,
    is_active boolean not null default true,
    created_at timestamptz not null default now()
);

create table if not exists usage_events (
    id uuid primary key default uuid_generate_v4(),
    api_key_id uuid not null references api_keys(id) on delete cascade,
    backend text not null,
    model text not null,
    prompt_tokens bigint not null default 0,
    completion_tokens bigint not null default 0,
    cost_usd numeric(10, 6) not null default 0,
    execution_time_s numeric(10, 3) not null default 0,
    status text not null,                          -- 'ok' | 'error' | 'timeout'
    created_at timestamptz not null default now()
);

create index if not exists idx_usage_events_api_key_id on usage_events(api_key_id);
create index if not exists idx_usage_events_created_at on usage_events(created_at);

-- Atomic increment so concurrent requests don't clobber each other's usage counters.
create or replace function increment_tokens_used(key_id uuid, delta bigint)
returns void as $$
begin
    update api_keys
    set tokens_used_this_period = tokens_used_this_period + delta
    where id = key_id;
end;
$$ language plpgsql;

-- Row Level Security: locked down. Only the service-role key (used exclusively by
-- the backend, never shipped to a client) can read/write these tables.
alter table api_keys enable row level security;
alter table usage_events enable row level security;
