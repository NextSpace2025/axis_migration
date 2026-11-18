begin;
create schema if not exists axis_viewer;
revoke all on schema axis_viewer from public, anon, authenticated;

create table if not exists axis_viewer.datasets (
  id text primary key,
  label text not null,
  description text not null,
  default_table text not null,
  catalog jsonb not null,
  graph jsonb not null
);
create table if not exists axis_viewer.tables (
  dataset text references axis_viewer.datasets on delete cascade,
  name text,
  metadata jsonb not null,
  primary key (dataset, name)
);
create table if not exists axis_viewer.rows (
  dataset text,
  table_name text,
  row_key bigint,
  payload jsonb not null,
  binding jsonb not null,
  file_ids text[] not null,
  search_text text not null,
  primary key (dataset, table_name, row_key),
  foreign key (dataset, table_name) references axis_viewer.tables on delete cascade
);
create index if not exists axis_viewer_rows_files on axis_viewer.rows using gin(file_ids);
revoke all on all tables in schema axis_viewer from public, anon, authenticated;
commit;
