begin;
alter table axis_viewer.datasets drop constraint if exists datasets_access_code_check;
alter table axis_viewer.datasets add constraint datasets_access_code_check
  check (access_code ~ '^[0-9]{20}$') not valid;
commit;
