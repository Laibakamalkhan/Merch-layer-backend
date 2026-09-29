-- Supabase SQL Editor mein poora paste karke Run karein.
-- Result mein sirf wo cheezein aayengi jo MISSING hain.
-- Agar sab theek hai to sirf ek row aayegi: OK | Sab kuch maujood hai

with expected_tables(s, t) as (
  values
    ('ai','conversations'),
    ('ai','dashboard_specs'),
    ('ai','document_chunks'),
    ('ai','documents'),
    ('ai','embedding_jobs'),
    ('ai','generated_queries'),
    ('ai','messages'),
    ('ai','metric_definitions'),
    ('ai','query_permissions'),
    ('ai','query_runs'),
    ('ai','semantic_columns'),
    ('bronze','raw_objects'),
    ('bronze','records'),
    ('bronze','schema_snapshots'),
    ('control','connection_credentials'),
    ('control','connection_resources'),
    ('control','connections'),
    ('control','platform_resources'),
    ('control','platform_versions'),
    ('control','platforms'),
    ('control','sync_schedules'),
    ('gold','channel_daily'),
    ('gold','customer_metrics'),
    ('gold','daily_sales'),
    ('gold','fulfillment_daily'),
    ('gold','inventory_snapshot_daily'),
    ('gold','product_daily'),
    ('gold','refund_daily'),
    ('iam','profiles'),
    ('iam','tenant_members'),
    ('iam','tenants'),
    ('ingestion','checkpoints'),
    ('ingestion','extraction_pages'),
    ('ingestion','pipeline_stage_runs'),
    ('ingestion','sync_job_connections'),
    ('ingestion','sync_jobs'),
    ('ingestion','sync_runs'),
    ('ingestion','webhook_events'),
    ('ops','audit_logs'),
    ('ops','data_quality_results'),
    ('ops','data_quality_runs'),
    ('ops','errors'),
    ('ops','job_events'),
    ('ops','usage_daily'),
    ('silver','categories'),
    ('silver','customer_addresses'),
    ('silver','customers'),
    ('silver','fulfillment_items'),
    ('silver','fulfillments'),
    ('silver','inventory_levels'),
    ('silver','locations'),
    ('silver','order_addresses'),
    ('silver','order_items'),
    ('silver','orders'),
    ('silver','payments'),
    ('silver','product_categories'),
    ('silver','product_variants'),
    ('silver','products'),
    ('silver','refund_items'),
    ('silver','refunds'),
    ('silver','return_items'),
    ('silver','returns')
),
problems as (
  -- 1) tables (62)
  select 'table' as kind, e.s || '.' || e.t as name
  from expected_tables e
  where not exists (
    select 1 from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = e.s and c.relname = e.t and c.relkind in ('r','p','v','m')
  )
  union all
  -- 2) app.* functions jo backend bulata hai
  select 'function', 'app.' || f
  from unnest(array[
    'finalize_job_status','get_connection_secret','initialize_connection_resources',
    'store_connection_secret','upsert_checkpoint'
  ]) as f
  where not exists (
    select 1 from pg_proc p join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'app' and p.proname = f
  )
  union all
  -- 3) pgvector (AI search ke liye), 'extensions' schema mein hona chahiye
  select 'extension', 'vector (extensions schema mein)'
  where not exists (
    select 1 from pg_extension x join pg_namespace n on n.oid = x.extnamespace
    where x.extname = 'vector' and n.nspname = 'extensions'
  )
  union all
  -- 4) Supabase Vault (store credentials ke liye)
  select 'extension', 'supabase_vault'
  where not exists (select 1 from pg_extension where extname = 'supabase_vault')
  union all
  -- 5) Storage buckets
  select 'storage bucket', b
  from unnest(array['commerce-bronze','commerce-files']) as b
  where not exists (select 1 from storage.buckets where name = b)
)
select kind, name from problems
union all
select 'OK', 'Sab kuch maujood hai' where not exists (select 1 from problems)
order by kind, name;
