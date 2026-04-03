"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { ArrowRight, FolderSearch2, LoaderCircle, RefreshCw, Waypoints } from "lucide-react";
import { toast } from "sonner";

import type {
  ArchiveContentType,
  EnrichmentRun,
  EnrichmentRunStatusDto,
  SyncRun,
  SourceConnection,
  SyncCoverageKind,
  SyncRunStatusDto,
} from "@/entities/archive/model";
import { Header } from "@/features/navigation/ui/Header";
import { useAuth } from "@/app/providers/auth/useAuth";
import {
  createArchiveSource,
  listArchiveEnrichmentRuns,
  listArchiveSources,
  listArchiveSyncs,
  startArchiveEnrichmentRun,
  startArchiveSync,
  updateArchiveSource,
} from "@/shared/api/archive";
import { Button } from "@/shared/components/ui/button";
import { Card } from "@/shared/components/ui/card";
import { Checkbox } from "@/shared/components/ui/checkbox";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/components/ui/select";
import { useI18n } from "@/shared/i18n/I18nProvider";
import { AdminAccessGate } from "@/widgets/access/ui/admin-access-gate";

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (typeof error === "object" && error !== null) {
    const response = "response" in error ? (error as { response?: { data?: unknown } }).response : undefined;
    const data = response?.data;
    if (typeof data === "object" && data !== null && "detail" in data) {
      const detail = (data as { detail?: unknown }).detail;
      if (typeof detail === "string" && detail.trim()) {
        return detail;
      }
    }
  }
  return fallback;
};

const toSyncRunStatusDto = (sync: SyncRun, source?: SourceConnection): SyncRunStatusDto => {
  const completedItems = Math.max(sync.total_items - sync.queued_items - sync.processing_items, 0);
  const progress = sync.total_items > 0 ? Math.min(completedItems / sync.total_items, 1) : 0;

  return {
    sync_run_id: sync.id,
    source_id: sync.source_id,
    source_display_name: source?.display_name ?? sync.source_id,
    source_kind: source?.kind ?? "custom",
    status: sync.status,
    coverage_kind: sync.coverage_kind,
    total_items: sync.total_items,
    new_items: sync.new_items,
    updated_items: sync.updated_items,
    unchanged_items: sync.unchanged_items,
    queued_items: sync.queued_items,
    processing_items: sync.processing_items,
    indexed_items: sync.indexed_items,
    failed_items: sync.failed_items,
    skipped_items: sync.skipped_items,
    progress,
    started_at: sync.started_at,
    completed_at: sync.completed_at,
    created_at: sync.created_at,
    updated_at: sync.updated_at,
  };
};

const toEnrichmentRunStatusDto = (run: EnrichmentRun): EnrichmentRunStatusDto => {
  const processedItems = run.completed_items + run.failed_items;
  const progress = run.total_items > 0 ? Math.min(processedItems / run.total_items, 1) : 0;

  return {
    enrichment_run_id: run.id,
    status: run.status,
    source_ids: run.source_ids,
    content_types: run.content_types,
    present_in_latest_sync: run.present_in_latest_sync,
    sample_percent: run.sample_percent,
    total_items: run.total_items,
    queued_items: run.queued_items,
    processing_items: run.processing_items,
    completed_items: run.completed_items,
    failed_items: run.failed_items,
    progress,
    started_at: run.started_at,
    completed_at: run.completed_at,
    created_at: run.created_at,
    updated_at: run.updated_at,
  };
};

export default function ArchiveAdminPage() {
  const { t } = useI18n();
  const auth = useAuth();
  const queryClient = useQueryClient();
  const roles = auth?.user?.role_slugs ?? auth?.user?.roles ?? [];
  const isAdmin = roles.includes("admin");

  const [displayName, setDisplayName] = useState("Telegram Archive");
  const [slug, setSlug] = useState("telegram-main");
  const [exportPath, setExportPath] = useState("/Users/laughinme/Downloads/AyuGram Desktop/ChatExport_2026-03-23");
  const [coverageKind, setCoverageKind] = useState<SyncCoverageKind>("full_snapshot");
  const [samplePercent, setSamplePercent] = useState("20");
  const [excludeVideoNotes, setExcludeVideoNotes] = useState(true);
  const [enrichmentSamplePercent, setEnrichmentSamplePercent] = useState("15");
  const [enrichmentPresentOnly, setEnrichmentPresentOnly] = useState(true);

  const sourcesQuery = useQuery({
    queryKey: ["archive-sources", "admin"],
    queryFn: listArchiveSources,
    enabled: isAdmin,
    refetchInterval: 30000,
  });

  const sourceIds = useMemo(() => (sourcesQuery.data ?? []).map((source) => source.id), [sourcesQuery.data]);

  const syncsQuery = useQuery({
    queryKey: ["archive-syncs", ...sourceIds],
    enabled: isAdmin && sourceIds.length > 0,
    queryFn: async () => {
      const sourceById = new Map((sourcesQuery.data ?? []).map((source) => [source.id, source]));
      const syncLists = await Promise.all(sourceIds.map((sourceId) => listArchiveSyncs(sourceId, 8)));
      return syncLists.flat().map((sync) => toSyncRunStatusDto(sync, sourceById.get(sync.source_id)));
    },
    refetchInterval: 30000,
  });

  const enrichmentRunsQuery = useQuery({
    queryKey: ["archive-enrichment-runs", ...sourceIds],
    enabled: isAdmin && sourceIds.length > 0,
    queryFn: async () => {
      const runLists = await Promise.all(sourceIds.map((sourceId) => listArchiveEnrichmentRuns(sourceId, 8)));
      return runLists.flat().map(toEnrichmentRunStatusDto);
    },
    refetchInterval: 30000,
  });

  const createSourceMutation = useMutation({
    mutationFn: createArchiveSource,
    onSuccess: async () => {
      toast.success(t("archiveAdmin.sourceCreated"));
      await queryClient.invalidateQueries({ queryKey: ["archive-sources"] });
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, t("archiveAdmin.sourceCreateFailed")));
    },
  });

  const updateSourceMutation = useMutation({
    mutationFn: ({ sourceId, status }: { sourceId: string; status: "active" | "paused" }) =>
      updateArchiveSource(sourceId, { status }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["archive-sources"] });
    },
  });

  const startSyncMutation = useMutation({
    mutationFn: ({ sourceId }: { sourceId: string }) =>
      startArchiveSync(sourceId, {
        coverage_kind: coverageKind,
        sample_percent: coverageKind === "partial_sample" ? Number.parseInt(samplePercent, 10) || null : null,
        exclude_content_types: excludeVideoNotes ? ["video_note"] : [],
      }),
    onSuccess: async () => {
      toast.success(t("archiveAdmin.syncStarted"));
      await queryClient.invalidateQueries({ queryKey: ["archive-syncs"] });
      await queryClient.invalidateQueries({ queryKey: ["archive-sources"] });
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, t("archiveAdmin.syncStartFailed")));
    },
  });

  const startEnrichmentMutation = useMutation({
    mutationFn: ({ sourceId }: { sourceId: string }) =>
      startArchiveEnrichmentRun({
        source_ids: [sourceId],
        content_types: ["text", "photo", "voice", "audio", "video"] satisfies ArchiveContentType[],
        present_in_latest_sync: enrichmentPresentOnly ? true : null,
        sample_percent: Number.parseInt(enrichmentSamplePercent, 10) || null,
      }),
    onSuccess: async () => {
      toast.success(t("archiveAdmin.enrichmentStarted"));
      await queryClient.invalidateQueries({ queryKey: ["archive-enrichment-runs"] });
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, t("archiveAdmin.enrichmentStartFailed")));
    },
  });

  const syncsBySource = useMemo(() => {
    const map = new Map<string, SyncRunStatusDto[]>();
    for (const entry of syncsQuery.data ?? []) {
      const existing = map.get(entry.source_id) ?? [];
      existing.push(entry);
      map.set(entry.source_id, existing);
    }
    for (const value of map.values()) {
      value.sort((left, right) => right.created_at.localeCompare(left.created_at));
    }
    return map;
  }, [syncsQuery.data]);

  const syncsErrorMessage = syncsQuery.isError
    ? getErrorMessage(syncsQuery.error, t("archiveAdmin.syncStatusLoadFailed"))
    : null;

  const enrichmentRunsBySource = useMemo(() => {
    const map = new Map<string, EnrichmentRunStatusDto[]>();
    for (const entry of enrichmentRunsQuery.data ?? []) {
      for (const sourceId of entry.source_ids) {
        const existing = map.get(sourceId) ?? [];
        existing.push(entry);
        map.set(sourceId, existing);
      }
    }
    for (const value of map.values()) {
      value.sort((left, right) => right.created_at.localeCompare(left.created_at));
    }
    return map;
  }, [enrichmentRunsQuery.data]);

  const enrichmentErrorMessage = enrichmentRunsQuery.isError
    ? getErrorMessage(enrichmentRunsQuery.error, t("archiveAdmin.enrichmentStatusLoadFailed"))
    : null;

  const activeSyncs = useMemo(
    () => (syncsQuery.data ?? []).filter((run) => run.status === "scanning" || run.status === "indexing"),
    [syncsQuery.data],
  );

  const activeEnrichmentRuns = useMemo(
    () => (enrichmentRunsQuery.data ?? []).filter((run) => run.status === "created" || run.status === "running"),
    [enrichmentRunsQuery.data],
  );

  const liveQueueLoad = useMemo(() => {
    const syncLoad = activeSyncs.reduce(
      (acc, run) => acc + run.queued_items + run.processing_items,
      0,
    );
    const enrichmentLoad = activeEnrichmentRuns.reduce(
      (acc, run) => acc + run.queued_items + run.processing_items,
      0,
    );
    return syncLoad + enrichmentLoad;
  }, [activeEnrichmentRuns, activeSyncs]);

  const knownCorpusItems = useMemo(() => {
    const latestSyncBySource = new Map<string, SyncRunStatusDto>();
    for (const run of syncsQuery.data ?? []) {
      const previous = latestSyncBySource.get(run.source_id);
      if (!previous || run.created_at > previous.created_at) {
        latestSyncBySource.set(run.source_id, run);
      }
    }
    return Array.from(latestSyncBySource.values()).reduce(
      (acc, run) => acc + run.new_items + run.updated_items + run.unchanged_items,
      0,
    );
  }, [syncsQuery.data]);

  const handleCreateSource = async () => {
    await createSourceMutation.mutateAsync({
      kind: "telegram_desktop_export",
      slug: slug.trim(),
      display_name: displayName.trim(),
      config_json: {
        export_path: exportPath.trim(),
      },
    });
  };

  const renderSyncCard = (syncRun: SyncRunStatusDto) => {
    const progress = Math.round(syncRun.progress * 100);
    return (
      <div key={syncRun.sync_run_id} className="rounded-2xl border border-border/70 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="font-semibold">{syncRun.coverage_kind}</p>
            <p className="text-sm text-muted-foreground">{new Date(syncRun.created_at).toLocaleString()}</p>
          </div>
          <span className="rounded-full border border-border/70 px-3 py-1 text-xs uppercase tracking-[0.22em] text-muted-foreground">
            {syncRun.status}
          </span>
        </div>
        <div className="mt-4 h-2 overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full bg-foreground transition-all" style={{ width: `${progress}%` }} />
        </div>
        <div className="mt-3 flex flex-wrap gap-4 text-sm text-muted-foreground">
          <span>{t("archiveAdmin.total")}: {syncRun.total_items}</span>
          <span>{t("archiveAdmin.newItems")}: {syncRun.new_items}</span>
          <span>{t("archiveAdmin.updatedItems")}: {syncRun.updated_items}</span>
          <span>{t("archiveAdmin.unchangedItems")}: {syncRun.unchanged_items}</span>
          <span>{t("archiveAdmin.indexed")}: {syncRun.indexed_items}</span>
          <span>{t("archiveAdmin.failed")}: {syncRun.failed_items}</span>
          <span>{t("archiveAdmin.skipped")}: {syncRun.skipped_items}</span>
        </div>
        <div className="mt-3 flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {progress}% · {syncRun.source_display_name} · {t("archiveAdmin.queued")}: {syncRun.queued_items} · {t("archiveAdmin.processing")}: {syncRun.processing_items}
          </span>
          <Button asChild variant="ghost" size="sm">
            <Link href="/archive">
              {t("archiveAdmin.openSearch")}
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
        </div>
      </div>
    );
  };

  const renderEnrichmentCard = (run: EnrichmentRunStatusDto) => {
    const progress = Math.round(run.progress * 100);
    return (
      <div key={run.enrichment_run_id} className="rounded-2xl border border-border/70 bg-muted/20 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="font-semibold">derived_text backfill</p>
            <p className="text-sm text-muted-foreground">{new Date(run.created_at).toLocaleString()}</p>
          </div>
          <span className="rounded-full border border-border/70 px-3 py-1 text-xs uppercase tracking-[0.22em] text-muted-foreground">
            {run.status}
          </span>
        </div>
        <div className="mt-4 h-2 overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full bg-foreground transition-all" style={{ width: `${progress}%` }} />
        </div>
        <div className="mt-3 flex flex-wrap gap-4 text-sm text-muted-foreground">
          <span>{t("archiveAdmin.total")}: {run.total_items}</span>
          <span>{t("archiveAdmin.completed")}: {run.completed_items}</span>
          <span>{t("archiveAdmin.failed")}: {run.failed_items}</span>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <AdminAccessGate
        requiredRoles={["admin"]}
        accessDeniedTitle={t("archive.accessDeniedTitle")}
        accessDeniedBody={t("archive.accessDeniedBody")}
      >
        <main className="mx-auto flex max-w-7xl flex-col gap-8 px-4 py-12">
          <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
            <motion.div
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.28 }}
              className="space-y-5"
            >
              <p className="text-sm font-semibold uppercase tracking-[0.28em] text-muted-foreground">
                {t("archiveAdmin.eyebrow")}
              </p>
              <h1 className="text-4xl font-black tracking-tight sm:text-5xl">
                {t("archiveAdmin.title")}
              </h1>
              <p className="max-w-3xl text-lg text-muted-foreground">{t("archiveAdmin.subtitle")}</p>
              <div className="flex flex-wrap gap-3">
                <Button asChild variant="outline" size="lg">
                  <Link href="/archive">{t("archiveAdmin.openSearch")}</Link>
                </Button>
              </div>
            </motion.div>

          <Card className="border-border/70 p-6">
            <div className="flex items-start gap-4">
                <div className="rounded-2xl border border-border/70 bg-muted/20 p-3">
                  <FolderSearch2 className="h-5 w-5 text-foreground" />
                </div>
                <div>
                  <p className="font-semibold">{t("archiveAdmin.noteTitle")}</p>
                  <p className="mt-2 text-sm text-muted-foreground">{t("archiveAdmin.noteBody")}</p>
                </div>
            </div>
          </Card>

          <Card className="border-border/70 p-6">
            <p className="text-sm font-semibold uppercase tracking-[0.28em] text-muted-foreground">
              {t("archiveAdmin.liveEyebrow")}
            </p>
            <h2 className="mt-3 text-2xl font-black tracking-tight">{t("archiveAdmin.liveTitle")}</h2>
            <p className="mt-3 text-sm text-muted-foreground">{t("archiveAdmin.liveBody")}</p>
            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              <div className="rounded-2xl border border-border/70 bg-muted/20 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-muted-foreground">{t("archiveAdmin.activeSyncs")}</p>
                <p className="mt-3 text-3xl font-black tracking-tight">{activeSyncs.length}</p>
              </div>
              <div className="rounded-2xl border border-border/70 bg-muted/20 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-muted-foreground">{t("archiveAdmin.activeEnrichments")}</p>
                <p className="mt-3 text-3xl font-black tracking-tight">{activeEnrichmentRuns.length}</p>
              </div>
              <div className="rounded-2xl border border-border/70 bg-muted/20 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-muted-foreground">{t("archiveAdmin.knownCorpus")}</p>
                <p className="mt-3 text-3xl font-black tracking-tight">{knownCorpusItems}</p>
              </div>
            </div>
            <div className="mt-4 rounded-2xl border border-border/70 bg-muted/20 p-4 text-sm text-muted-foreground">
              {t("archiveAdmin.liveQueue")}: {liveQueueLoad}
            </div>
          </Card>
          </section>

          <Card className="border-border/70 p-6">
            <div className="grid gap-4 lg:grid-cols-[1fr_220px_1fr_auto] lg:items-end">
              <div className="space-y-3">
                <Label htmlFor="archive-display-name">{t("archiveAdmin.sourceNameLabel")}</Label>
                <Input id="archive-display-name" value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
              </div>
              <div className="space-y-3">
                <Label htmlFor="archive-slug">{t("archiveAdmin.sourceSlugLabel")}</Label>
                <Input id="archive-slug" value={slug} onChange={(event) => setSlug(event.target.value)} />
              </div>
              <div className="space-y-3">
                <Label htmlFor="archive-source-path">{t("archiveAdmin.pathLabel")}</Label>
                <Input
                  id="archive-source-path"
                  value={exportPath}
                  onChange={(event) => setExportPath(event.target.value)}
                  placeholder={t("archiveAdmin.pathPlaceholder")}
                />
              </div>
              <Button
                className="lg:min-w-52"
                onClick={() => void handleCreateSource()}
                disabled={createSourceMutation.isPending || !displayName.trim() || !slug.trim() || !exportPath.trim()}
              >
                {createSourceMutation.isPending ? (
                  <>
                    <LoaderCircle className="mr-2 h-4 w-4 animate-spin" />
                    {t("archiveAdmin.creatingSource")}
                  </>
                ) : (
                  t("archiveAdmin.createSource")
                )}
              </Button>
            </div>
            <p className="mt-3 text-sm text-muted-foreground">{t("archiveAdmin.pathHint")}</p>
          </Card>

          <Card className="border-border/70 p-6">
            <div className="grid gap-4 lg:grid-cols-[220px_180px_1fr] lg:items-end">
              <div className="space-y-3">
                <Label>{t("archiveAdmin.coverageKindLabel")}</Label>
                <Select value={coverageKind} onValueChange={(value) => setCoverageKind(value as SyncCoverageKind)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="full_snapshot">{t("archiveAdmin.coverage.full_snapshot")}</SelectItem>
                    <SelectItem value="partial_sample">{t("archiveAdmin.coverage.partial_sample")}</SelectItem>
                    <SelectItem value="incremental">{t("archiveAdmin.coverage.incremental")}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-3">
                <Label htmlFor="archive-sample-percent">{t("archiveAdmin.samplePercentLabel")}</Label>
                <Input
                  id="archive-sample-percent"
                  type="number"
                  min={1}
                  max={100}
                  value={samplePercent}
                  disabled={coverageKind !== "partial_sample"}
                  onChange={(event) => setSamplePercent(event.target.value)}
                />
              </div>
              <label className="flex items-center gap-3 rounded-2xl border border-border/70 bg-muted/20 px-4 py-3 text-sm">
                <Checkbox checked={excludeVideoNotes} onCheckedChange={(checked) => setExcludeVideoNotes(checked === true)} />
                <span>{t("archiveAdmin.excludeVideoNotesLabel")}</span>
              </label>
            </div>
            <p className="mt-3 text-sm text-muted-foreground">{t("archiveAdmin.syncConfigHint")}</p>
          </Card>

          <Card className="border-border/70 p-6">
            <div className="grid gap-4 lg:grid-cols-[200px_1fr] lg:items-end">
              <div className="space-y-3">
                <Label htmlFor="archive-enrichment-sample">{t("archiveAdmin.enrichmentSampleLabel")}</Label>
                <Input
                  id="archive-enrichment-sample"
                  type="number"
                  min={1}
                  max={100}
                  value={enrichmentSamplePercent}
                  onChange={(event) => setEnrichmentSamplePercent(event.target.value)}
                />
              </div>
              <label className="flex items-center gap-3 rounded-2xl border border-border/70 bg-muted/20 px-4 py-3 text-sm">
                <Checkbox checked={enrichmentPresentOnly} onCheckedChange={(checked) => setEnrichmentPresentOnly(checked === true)} />
                <span>{t("archiveAdmin.enrichmentPresentOnlyLabel")}</span>
              </label>
            </div>
            <p className="mt-3 text-sm text-muted-foreground">{t("archiveAdmin.enrichmentConfigHint")}</p>
          </Card>

          <section className="grid gap-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold uppercase tracking-[0.28em] text-muted-foreground">
                  {t("archiveAdmin.historyEyebrow")}
                </p>
                <h2 className="mt-2 text-2xl font-black tracking-tight">{t("archiveAdmin.historyTitle")}</h2>
              </div>
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  void sourcesQuery.refetch();
                  void syncsQuery.refetch();
                  void enrichmentRunsQuery.refetch();
                }}
                disabled={sourcesQuery.isFetching || syncsQuery.isFetching || enrichmentRunsQuery.isFetching}
              >
                <RefreshCw className={`mr-2 h-4 w-4 ${sourcesQuery.isFetching ? "animate-spin" : ""}`} />
                {t("archiveAdmin.refresh")}
              </Button>
            </div>

            {(sourcesQuery.data ?? []).length === 0 ? (
              <Card className="border-border/70 p-8 text-center text-muted-foreground">
                {t("archiveAdmin.empty")}
              </Card>
            ) : (
              (sourcesQuery.data ?? []).map((source) => {
                const syncs = syncsBySource.get(source.id) ?? [];
                const enrichmentRuns = enrichmentRunsBySource.get(source.id) ?? [];
                return (
                  <motion.article
                    key={source.id}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.22 }}
                  >
                    <Card className="border-border/70 p-5">
                      <div className="flex flex-col gap-5">
                        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                          <div className="space-y-2">
                            <div className="flex flex-wrap items-center gap-3">
                              <p className="text-lg font-semibold">{source.display_name}</p>
                              <span className="rounded-full border border-border/70 px-3 py-1 text-xs uppercase tracking-[0.24em] text-muted-foreground">
                                {source.kind}
                              </span>
                              <span className="rounded-full border border-border/70 px-3 py-1 text-xs uppercase tracking-[0.24em] text-muted-foreground">
                                {source.status}
                              </span>
                            </div>
                            <p className="text-sm text-muted-foreground">{source.slug}</p>
                            <p className="text-sm text-muted-foreground">{String(source.config_json["export_path"] ?? "")}</p>
                          </div>

                          <div className="flex flex-wrap gap-3">
                            <Button
                              type="button"
                              variant="outline"
                              onClick={() => updateSourceMutation.mutate({ sourceId: source.id, status: source.status === "active" ? "paused" : "active" })}
                              disabled={updateSourceMutation.isPending}
                            >
                              <Waypoints className="mr-2 h-4 w-4" />
                              {source.status === "active" ? t("archiveAdmin.pauseSource") : t("archiveAdmin.activateSource")}
                            </Button>
                            <Button
                              type="button"
                              onClick={() => startSyncMutation.mutate({ sourceId: source.id })}
                              disabled={startSyncMutation.isPending || source.status !== "active"}
                            >
                              {startSyncMutation.isPending ? (
                                <>
                                  <LoaderCircle className="mr-2 h-4 w-4 animate-spin" />
                                  {t("archiveAdmin.starting")}
                                </>
                              ) : (
                                t("archiveAdmin.startSync")
                              )}
                            </Button>
                            <Button
                              type="button"
                              variant="secondary"
                              onClick={() => startEnrichmentMutation.mutate({ sourceId: source.id })}
                              disabled={startEnrichmentMutation.isPending || source.status !== "active"}
                            >
                              {startEnrichmentMutation.isPending ? (
                                <>
                                  <LoaderCircle className="mr-2 h-4 w-4 animate-spin" />
                                  {t("archiveAdmin.startingEnrichment")}
                                </>
                              ) : (
                                t("archiveAdmin.startEnrichment")
                              )}
                            </Button>
                          </div>
                        </div>

                        {syncsErrorMessage ? (
                          <div className="rounded-2xl border border-dashed border-destructive/40 bg-destructive/5 p-5 text-sm text-destructive">
                            {syncsErrorMessage}
                          </div>
                        ) : syncs.length === 0 ? (
                          <div className="rounded-2xl border border-dashed border-border/70 p-5 text-sm text-muted-foreground">
                            {t("archiveAdmin.noSyncsYet")}
                          </div>
                        ) : (
                          <div className="grid gap-3">{syncs.map((syncRun) => renderSyncCard(syncRun))}</div>
                        )}

                        <div className="space-y-3">
                          <p className="text-sm font-semibold uppercase tracking-[0.24em] text-muted-foreground">
                            {t("archiveAdmin.enrichmentHistoryTitle")}
                          </p>
                          {enrichmentErrorMessage ? (
                            <div className="rounded-2xl border border-dashed border-destructive/40 bg-destructive/5 p-5 text-sm text-destructive">
                              {enrichmentErrorMessage}
                            </div>
                          ) : enrichmentRuns.length === 0 ? (
                            <div className="rounded-2xl border border-dashed border-border/70 p-5 text-sm text-muted-foreground">
                              {t("archiveAdmin.noEnrichmentRunsYet")}
                            </div>
                          ) : (
                            <div className="grid gap-3">{enrichmentRuns.map((run) => renderEnrichmentCard(run))}</div>
                          )}
                        </div>
                      </div>
                    </Card>
                  </motion.article>
                );
              })
            )}
          </section>
        </main>
      </AdminAccessGate>
    </div>
  );
}
