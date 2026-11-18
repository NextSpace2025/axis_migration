begin;
create schema if not exists axis_viewer;
revoke all on schema axis_viewer from public, anon, authenticated;

create table if not exists axis_viewer.analysis_tests (
  code text primary key check (code ~ '^[0-9]{6}$'),
  numbers smallint[] not null check (
    cardinality(numbers) = 6 and array_ndims(numbers) = 1
    and array_position(numbers, null) is null
    and 1 <= all(numbers) and 100 >= all(numbers)
  )
);
alter table axis_viewer.analysis_tests enable row level security;
revoke all on axis_viewer.analysis_tests from public, anon, authenticated;
commit;
