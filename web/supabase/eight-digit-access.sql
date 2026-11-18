begin;
alter table axis_viewer.datasets drop constraint if exists datasets_access_code_check;
alter table axis_viewer.datasets add constraint datasets_access_code_check
  check (access_code ~ '^[0-9]{8}$') not valid;

create table if not exists axis_viewer.lookup_failures (
  bucket text not null,
  window_start timestamptz not null,
  failures integer not null,
  primary key (bucket, window_start)
);
alter table axis_viewer.lookup_failures enable row level security;
revoke all on axis_viewer.lookup_failures from public, anon, authenticated;

create or replace function axis_viewer.open_result_code(entered_code text, client_bucket text)
returns table(dataset_id text, landing_table text, retry_after integer)
language plpgsql security invoker
set search_path = pg_catalog
as $$
declare
  checked_at timestamptz := statement_timestamp();
  epoch timestamptz := '2000-01-01 00:00:00+00';
  global_window timestamptz := date_bin('1 hour', checked_at, epoch);
  client_window timestamptz := date_bin('15 minutes', checked_at, epoch);
  ip_bucket text := 'ip:' || client_bucket;
  blocked_until timestamptz;
begin
  if entered_code is null or entered_code !~ '^[0-9]{8}$'
     or client_bucket is null or client_bucket !~ '^[a-f0-9]{64}$' then
    return next;
    return;
  end if;

  -- The database lock makes the check and increment atomic across deployments.
  perform pg_advisory_xact_lock(hashtext('axis_viewer result lookup attempts'));

  select max(case when f.bucket = 'global' then f.window_start + interval '1 hour'
                  else f.window_start + interval '15 minutes' end)
    into blocked_until
    from axis_viewer.lookup_failures f
    where (f.bucket = 'global' and f.window_start = global_window and f.failures >= 24)
       or (f.bucket = ip_bucket and f.window_start = client_window and f.failures >= 5);

  if blocked_until is not null then
    retry_after := greatest(1, ceil(extract(epoch from blocked_until - checked_at))::integer);
    return next;
    return;
  end if;

  select d.id, d.default_table into dataset_id, landing_table
    from axis_viewer.datasets d where d.access_code = entered_code;
  if not found then
    delete from axis_viewer.lookup_failures where window_start < global_window - interval '1 hour';
    insert into axis_viewer.lookup_failures as f (bucket, window_start, failures)
      values ('global', global_window, 1), (ip_bucket, client_window, 1)
      on conflict (bucket, window_start) do update set failures = f.failures + 1;
  end if;
  return next;
end;
$$;
revoke execute on function axis_viewer.open_result_code(text,text) from public, anon, authenticated;
commit;
