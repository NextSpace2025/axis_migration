begin;
alter table axis_viewer.datasets add column if not exists access_code text
  check (access_code ~ '^[0-9]{8}$');
alter table axis_viewer.datasets add column if not exists snapshot_sha256 text;
create unique index if not exists axis_viewer_datasets_access_code
  on axis_viewer.datasets(access_code) where access_code is not null;
commit;
