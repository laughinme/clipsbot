export type SourceKind = "telegram_desktop_export" | "discord" | "custom";
export type SourceStatus = "active" | "paused";
export type SyncTriggerKind = "manual" | "scheduled";
export type SyncCoverageKind = "full_snapshot" | "partial_sample" | "incremental";
export type SyncRunStatus = "created" | "scanning" | "indexing" | "completed" | "failed";
export type EnrichmentRunStatus = "created" | "running" | "completed" | "failed";
export type EnrichmentTriggerKind = "sync" | "manual" | "scheduled";
export type ArchiveContentType =
  | "text"
  | "photo"
  | "voice"
  | "video_note"
  | "video"
  | "audio"
  | "document"
  | "service"
  | "sticker"
  | "animation"
  | "unknown";

export type SourceConnection = {
  id: string;
  kind: SourceKind;
  slug: string;
  display_name: string;
  status: SourceStatus;
  config_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type SourceCreatePayload = {
  kind: SourceKind;
  slug: string;
  display_name: string;
  config_json: Record<string, unknown>;
};

export type SourceUpdatePayload = {
  display_name?: string;
  status?: SourceStatus;
  config_json?: Record<string, unknown>;
};

export type SourceSyncCreatePayload = {
  trigger_kind?: SyncTriggerKind;
  coverage_kind?: SyncCoverageKind;
  sample_percent?: number | null;
  include_content_types?: ArchiveContentType[];
  exclude_content_types?: ArchiveContentType[];
};

export type SyncRun = {
  id: string;
  source_id: string;
  trigger_kind: SyncTriggerKind;
  coverage_kind: SyncCoverageKind;
  status: SyncRunStatus;
  cursor?: string | null;
  raw_manifest_object_key?: string | null;
  sample_percent?: number | null;
  include_content_types: ArchiveContentType[];
  exclude_content_types: ArchiveContentType[];
  total_items: number;
  new_items: number;
  updated_items: number;
  unchanged_items: number;
  indexed_items: number;
  failed_items: number;
  skipped_items: number;
  queued_items: number;
  processing_items: number;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type SyncRunStatusDto = {
  sync_run_id: string;
  source_id: string;
  source_display_name: string;
  source_kind: SourceKind;
  status: SyncRunStatus;
  coverage_kind: SyncCoverageKind;
  total_items: number;
  new_items: number;
  updated_items: number;
  unchanged_items: number;
  queued_items: number;
  processing_items: number;
  indexed_items: number;
  failed_items: number;
  skipped_items: number;
  progress: number;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type ArchiveSearchMedia = {
  id: string;
  kind: ArchiveContentType;
  mime_type?: string | null;
  original_filename?: string | null;
  duration_ms?: number | null;
  width?: number | null;
  height?: number | null;
  play_url?: string | null;
  download_url?: string | null;
};

export type ArchiveSearchItem = {
  corpus_item_id: string;
  source_id: string;
  source_kind: SourceKind;
  source_display_name: string;
  stable_key: string;
  score: number;
  content_type: ArchiveContentType;
  occurred_at: string;
  author_external_id?: string | null;
  author_name?: string | null;
  container_external_id?: string | null;
  container_name?: string | null;
  text_preview?: string | null;
  caption?: string | null;
  snippet?: string | null;
  snippet_source?: "text" | "caption" | "ocr" | "transcript" | "summary" | null;
  matched_projection_kinds: ("raw_multimodal" | "derived_text")[];
  media?: ArchiveSearchMedia | null;
};

export type ArchiveSearchResponse = {
  items: ArchiveSearchItem[];
};

export type ArchiveSearchItemResponse = {
  item: ArchiveSearchItem;
};

export type ArchiveSearchFilters = {
  source_ids?: string[];
  source_kinds?: SourceKind[];
  content_types?: ArchiveContentType[];
  author_external_ids?: string[];
  container_external_ids?: string[];
  date_from?: string | null;
  date_to?: string | null;
  present_in_latest_sync?: boolean | null;
};

export type ArchiveSearchPayload = {
  query: string;
  limit?: number;
  filters?: ArchiveSearchFilters;
};

export type EnrichmentRun = {
  id: string;
  source_id?: string | null;
  sync_run_id?: string | null;
  trigger_kind: EnrichmentTriggerKind;
  status: EnrichmentRunStatus;
  source_ids: string[];
  content_types: ArchiveContentType[];
  present_in_latest_sync?: boolean | null;
  sample_percent?: number | null;
  total_items: number;
  queued_items: number;
  processing_items: number;
  completed_items: number;
  failed_items: number;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type EnrichmentRunStatusDto = {
  enrichment_run_id: string;
  status: EnrichmentRunStatus;
  source_ids: string[];
  content_types: ArchiveContentType[];
  present_in_latest_sync?: boolean | null;
  sample_percent?: number | null;
  total_items: number;
  queued_items: number;
  processing_items: number;
  completed_items: number;
  failed_items: number;
  progress: number;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type EnrichmentRunCreatePayload = {
  source_ids?: string[];
  content_types?: ArchiveContentType[];
  present_in_latest_sync?: boolean | null;
  sample_percent?: number | null;
};
