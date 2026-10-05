-- ==============================================================================
-- Migration: Add Uploaded Datasets & Register File Upload Platform
-- Usage: Execute in Supabase SQL Editor
-- ==============================================================================

-- 1. Register file_upload platform in control.platforms using generic-file-feed manifest
INSERT INTO control.platforms (
    id,
    code,
    name,
    protocol,
    status,
    manifest_key,
    category
)
VALUES (
    gen_random_uuid(),
    'file_upload',
    'File Upload (CSV/XLSX/JSON)',
    'file',
    'active',
    'generic-file-feed',
    'custom'
)
ON CONFLICT (code) DO UPDATE SET
    name = excluded.name,
    manifest_key = excluded.manifest_key,
    status = 'active';

-- 2. Create ingestion.uploaded_datasets table
CREATE TABLE IF NOT EXISTS ingestion.uploaded_datasets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES iam.tenants(id) ON DELETE CASCADE,
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    connection_id UUID REFERENCES control.connections(id) ON DELETE SET NULL,
    filename TEXT NOT NULL,
    file_type TEXT NOT NULL CHECK (file_type IN ('csv', 'xlsx', 'json')),
    storage_path TEXT NOT NULL,
    byte_size BIGINT NOT NULL,
    checksum_sha256 TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'uploaded' CHECK (status IN ('uploaded', 'profiling', 'profiled', 'ingesting', 'completed', 'failed')),
    has_validation_errors BOOLEAN NOT NULL DEFAULT false,
    detected_entity TEXT,
    profile_summary JSONB DEFAULT '{}'::jsonb,
    mapping_config JSONB DEFAULT '{}'::jsonb,
    quality_summary JSONB DEFAULT '{}'::jsonb,
    row_count INT DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_dataset_connection_status CHECK (
        (status IN ('uploaded', 'profiling', 'profiled') AND connection_id IS NULL)
        OR (status IN ('ingesting', 'completed') AND connection_id IS NOT NULL)
        OR (status = 'failed')
    )
);

CREATE INDEX IF NOT EXISTS idx_uploaded_datasets_tenant 
ON ingestion.uploaded_datasets(tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_uploaded_datasets_connection 
ON ingestion.uploaded_datasets(connection_id);
