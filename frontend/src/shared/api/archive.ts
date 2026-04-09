import apiProtected, { apiPublic } from "./axiosInstance";
import type {
  ArchiveSearchItemResponse,
  ArchiveSearchPayload,
  ArchiveSearchResponse,
  EnrichmentRun,
  EnrichmentRunCreatePayload,
  EnrichmentRunStatusDto,
  SourceConnection,
  SourceCreatePayload,
  SourceUpdatePayload,
  SourceSyncCreatePayload,
  SyncRun,
  SyncRunStatusDto,
} from "@/entities/archive/model";

export const listArchiveSources = async (): Promise<SourceConnection[]> => {
  const response = await apiPublic.get<{ items: SourceConnection[] }>("/archive/sources");
  return response.data.items;
};

export const createArchiveSource = async (payload: SourceCreatePayload): Promise<SourceConnection> => {
  const response = await apiProtected.post<SourceConnection>("/archive/sources", payload);
  return response.data;
};

export const updateArchiveSource = async (
  sourceId: string,
  payload: SourceUpdatePayload,
): Promise<SourceConnection> => {
  const response = await apiProtected.patch<SourceConnection>(`/archive/sources/${sourceId}`, payload);
  return response.data;
};

export const listArchiveSyncs = async (sourceId: string, limit = 20): Promise<SyncRun[]> => {
  const response = await apiProtected.get<{ items: SyncRun[] }>(`/archive/sources/${sourceId}/syncs`, {
    params: { limit },
  });
  return response.data.items;
};

export const startArchiveSync = async (
  sourceId: string,
  payload: SourceSyncCreatePayload,
): Promise<SyncRun> => {
  const response = await apiProtected.post<SyncRun>(`/archive/sources/${sourceId}/syncs`, {
    trigger_kind: payload.trigger_kind ?? "manual",
    coverage_kind: payload.coverage_kind ?? "full_snapshot",
    sample_percent: payload.sample_percent ?? null,
    include_content_types: payload.include_content_types ?? [],
    exclude_content_types: payload.exclude_content_types ?? [],
  });
  return response.data;
};

export const getArchiveSyncStatus = async (syncRunId: string): Promise<SyncRunStatusDto> => {
  const response = await apiProtected.get<SyncRunStatusDto>(`/archive/syncs/${syncRunId}`);
  return response.data;
};

export const searchArchive = async (payload: ArchiveSearchPayload): Promise<ArchiveSearchResponse> => {
  const response = await apiPublic.post<ArchiveSearchResponse>("/archive/search", payload);
  return response.data;
};

export const getArchiveItem = async (corpusItemId: string): Promise<ArchiveSearchItemResponse> => {
  const response = await apiPublic.get<ArchiveSearchItemResponse>(`/archive/items/${corpusItemId}`);
  return response.data;
};

export const searchSimilarArchiveItems = async (
  corpusItemId: string,
  limit = 10,
): Promise<ArchiveSearchResponse> => {
  const response = await apiPublic.get<ArchiveSearchResponse>(`/archive/search/similar/${corpusItemId}`, {
    params: { limit },
  });
  return response.data;
};

export const listArchiveEnrichmentRuns = async (
  sourceId: string,
  limit = 20,
): Promise<EnrichmentRun[]> => {
  const response = await apiProtected.get<{ items: EnrichmentRun[] }>(`/archive/sources/${sourceId}/enrichment-runs`, {
    params: { limit },
  });
  return response.data.items;
};

export const startArchiveEnrichmentRun = async (
  payload: EnrichmentRunCreatePayload,
): Promise<EnrichmentRun> => {
  const response = await apiProtected.post<EnrichmentRun>("/archive/enrichment-runs", {
    source_ids: payload.source_ids ?? [],
    content_types: payload.content_types ?? [],
    present_in_latest_sync: payload.present_in_latest_sync ?? null,
    sample_percent: payload.sample_percent ?? null,
  });
  return response.data;
};

export const getArchiveEnrichmentRunStatus = async (
  enrichmentRunId: string,
): Promise<EnrichmentRunStatusDto> => {
  const response = await apiProtected.get<EnrichmentRunStatusDto>(`/archive/enrichment-runs/${enrichmentRunId}`);
  return response.data;
};
