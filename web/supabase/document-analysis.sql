begin;
create table if not exists axis_viewer.document_jobs (
  dataset text primary key references axis_viewer.datasets(id) on delete cascade,
  owner_hash text not null, documents jsonb not null
);
create table if not exists axis_viewer.document_topics (
  dataset text references axis_viewer.document_jobs(dataset) on delete cascade,
  topic text not null, attempt uuid not null, started timestamptz not null, result jsonb,
  primary key(dataset,topic)
);
create table if not exists axis_viewer.document_usage (
  day date not null, bucket text not null, calls integer not null, primary key(day,bucket)
);
alter table axis_viewer.document_jobs enable row level security;
alter table axis_viewer.document_topics enable row level security;
alter table axis_viewer.document_usage enable row level security;
revoke all on axis_viewer.document_jobs, axis_viewer.document_topics, axis_viewer.document_usage from public, anon, authenticated;
commit;
