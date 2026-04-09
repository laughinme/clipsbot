"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import { ExternalLink, Image as ImageIcon, Link2, Music4, Search, Sparkles, Video } from "lucide-react";

import type { ArchiveContentType, ArchiveSearchItem, SourceConnection } from "@/entities/archive/model";
import { Header } from "@/features/navigation/ui/Header";
import { getArchiveItem, listArchiveSources, searchArchive, searchSimilarArchiveItems } from "@/shared/api/archive";
import { Button } from "@/shared/components/ui/button";
import { Card } from "@/shared/components/ui/card";
import { Checkbox } from "@/shared/components/ui/checkbox";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { useI18n } from "@/shared/i18n/I18nProvider";

const SEARCHABLE_TYPES: ArchiveContentType[] = ["text", "photo", "voice", "video_note", "video", "audio"];

type ArchivePageProps = {
  initialItemId?: string;
};

const getContentTypeIcon = (type: ArchiveContentType) => {
  if (type === "photo") {
    return ImageIcon;
  }
  if (type === "voice" || type === "audio") {
    return Music4;
  }
  if (type === "video_note" || type === "video") {
    return Video;
  }
  return Sparkles;
};

const getSnippetBadgeLabel = (source: ArchiveSearchItem["snippet_source"]) => {
  if (source === "ocr") {
    return "OCR";
  }
  if (source === "transcript") {
    return "Transcript";
  }
  if (source === "summary") {
    return "Summary";
  }
  if (source === "caption") {
    return "Caption";
  }
  if (source === "text") {
    return "Text";
  }
  return null;
};

const parseTelegramLinkMeta = (item: ArchiveSearchItem) => {
  const stableKeyParts = item.stable_key.split(":");
  const stableKeyChatId =
    stableKeyParts.length >= 3 && stableKeyParts[0] === "telegram" ? stableKeyParts[1] : null;
  const stableKeyMessageId =
    stableKeyParts.length >= 3 && stableKeyParts[0] === "telegram" ? stableKeyParts[2] : null;
  const chatId = item.container_external_id || stableKeyChatId;

  if (!chatId || !stableKeyMessageId || !chatId.startsWith("-100")) {
    return null;
  }

  const channelId = chatId.slice(4);
  if (!channelId || !/^\d+$/.test(channelId) || !/^\d+$/.test(stableKeyMessageId)) {
    return null;
  }

  return {
    channelId,
    messageId: stableKeyMessageId,
  };
};

const buildArchiveItemHref = (item: ArchiveSearchItem) => `/archive/items/${item.corpus_item_id}`;

const buildTelegramOpenHref = (item: ArchiveSearchItem) => {
  const meta = parseTelegramLinkMeta(item);
  if (!meta) {
    return null;
  }
  return `tg://privatepost?channel=${meta.channelId}&post=${meta.messageId}`;
};

export default function ArchivePage({ initialItemId }: ArchivePageProps) {
  const { t } = useI18n();
  const [query, setQuery] = useState("");
  const [selectedTypes, setSelectedTypes] = useState<ArchiveContentType[]>(SEARCHABLE_TYPES);
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [authorIdsInput, setAuthorIdsInput] = useState("");
  const [containerIdsInput, setContainerIdsInput] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [presentOnly, setPresentOnly] = useState(false);
  const [results, setResults] = useState<ArchiveSearchItem[]>([]);

  const sourcesQuery = useQuery({
    queryKey: ["archive-sources", "search-page"],
    queryFn: listArchiveSources,
  });

  const initialItemQuery = useQuery({
    queryKey: ["archive-item", initialItemId],
    queryFn: () => getArchiveItem(initialItemId!),
    enabled: Boolean(initialItemId),
  });

  const searchMutation = useMutation({
    mutationFn: searchArchive,
    onSuccess: (response) => setResults(response.items),
  });

  const similarMutation = useMutation({
    mutationFn: ({ corpusItemId }: { corpusItemId: string }) => searchSimilarArchiveItems(corpusItemId, 12),
    onSuccess: (response) => setResults(response.items),
  });

  const handleToggleType = (type: ArchiveContentType, checked: boolean) => {
    setSelectedTypes((current) => {
      if (checked) {
        return current.includes(type) ? current : [...current, type];
      }
      return current.filter((item) => item !== type);
    });
  };

  const handleToggleSource = (sourceId: string, checked: boolean) => {
    setSelectedSourceIds((current) => {
      if (checked) {
        return current.includes(sourceId) ? current : [...current, sourceId];
      }
      return current.filter((item) => item !== sourceId);
    });
  };

  const parseStringList = (value: string) =>
    value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);

  const handleSearch = async () => {
    if (!query.trim()) {
      return;
    }
    await searchMutation.mutateAsync({
      query: query.trim(),
      limit: 20,
      filters: {
        content_types: selectedTypes,
        source_ids: selectedSourceIds,
        author_external_ids: parseStringList(authorIdsInput),
        container_external_ids: parseStringList(containerIdsInput),
        date_from: dateFrom ? new Date(dateFrom).toISOString() : null,
        date_to: dateTo ? new Date(dateTo).toISOString() : null,
        present_in_latest_sync: presentOnly ? true : null,
      },
    });
  };

  const sources = sourcesQuery.data ?? [];
  const displayedResults =
    results.length > 0 ? results : initialItemQuery.data?.item ? [initialItemQuery.data.item] : [];

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="mx-auto flex max-w-7xl flex-col gap-8 px-4 py-12">
          <section className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
            <motion.div
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.28 }}
              className="space-y-5"
            >
              <p className="text-sm font-semibold uppercase tracking-[0.28em] text-muted-foreground">
                {t("archive.eyebrow")}
              </p>
              <h1 className="text-4xl font-black tracking-tight sm:text-5xl">
                {t("archive.title")}
              </h1>
              <p className="max-w-3xl text-lg text-muted-foreground">{t("archive.subtitle")}</p>
              <div className="flex flex-wrap gap-3">
                <Button asChild variant="outline" size="lg">
                  <Link href="/catalog">{t("archive.openClips")}</Link>
                </Button>
                <Button asChild size="lg">
                  <Link href="/admin/archive">{t("archive.openImportTools")}</Link>
                </Button>
              </div>
            </motion.div>

            <Card className="border-border/70 p-6">
              <p className="text-sm font-semibold uppercase tracking-[0.28em] text-muted-foreground">
                {t("archive.surfaceTitle")}
              </p>
              <div className="mt-4 space-y-3 text-sm text-muted-foreground">
                <p>{t("archive.surfaceLine1")}</p>
                <p>{t("archive.surfaceLine2")}</p>
                <p>{t("archive.surfaceLine3")}</p>
              </div>
            </Card>
          </section>

          <Card className="border-border/70 p-6">
            <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
              <div className="space-y-4">
                <Label htmlFor="archive-query">{t("archive.searchLabel")}</Label>
                <div className="flex flex-col gap-3 sm:flex-row">
                  <Input
                    id="archive-query"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder={t("archive.searchPlaceholder")}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        void handleSearch();
                      }
                    }}
                  />
                  <Button onClick={() => void handleSearch()} disabled={searchMutation.isPending || !query.trim()}>
                    <Search className="mr-2 h-4 w-4" />
                    {searchMutation.isPending ? t("archive.searching") : t("archive.searchButton")}
                  </Button>
                </div>
                <div className="grid gap-3 sm:grid-cols-3">
                  {SEARCHABLE_TYPES.map((type) => (
                    <label key={type} className="flex items-center gap-3 rounded-2xl border border-border/70 px-3 py-3 text-sm">
                      <Checkbox
                        checked={selectedTypes.includes(type)}
                        onCheckedChange={(checked) => handleToggleType(type, checked === true)}
                      />
                      <span>{t(`archive.types.${type}`)}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="space-y-4">
                <div className="space-y-3">
                  <Label>{t("archive.sourceFilterLabel")}</Label>
                  <div className="grid gap-2">
                    {sources.length === 0 ? (
                      <p className="text-sm text-muted-foreground">{t("archive.sourceFilterEmpty")}</p>
                    ) : (
                      sources.map((source: SourceConnection) => (
                        <label
                          key={source.id}
                          className="flex items-center gap-3 rounded-2xl border border-border/70 px-3 py-3 text-sm"
                        >
                          <Checkbox
                            checked={selectedSourceIds.includes(source.id)}
                            onCheckedChange={(checked) => handleToggleSource(source.id, checked === true)}
                          />
                          <span>{source.display_name}</span>
                        </label>
                      ))
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground">{t("archive.sourceFilterHint")}</p>
                </div>

                <div className="grid gap-3">
                  <div className="space-y-2">
                    <Label htmlFor="archive-authors">{t("archive.authorFilterLabel")}</Label>
                    <Input
                      id="archive-authors"
                      value={authorIdsInput}
                      onChange={(event) => setAuthorIdsInput(event.target.value)}
                      placeholder={t("archive.authorFilterPlaceholder")}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="archive-containers">{t("archive.containerFilterLabel")}</Label>
                    <Input
                      id="archive-containers"
                      value={containerIdsInput}
                      onChange={(event) => setContainerIdsInput(event.target.value)}
                      placeholder={t("archive.containerFilterPlaceholder")}
                    />
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="archive-date-from">{t("archive.dateFromLabel")}</Label>
                      <Input id="archive-date-from" type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="archive-date-to">{t("archive.dateToLabel")}</Label>
                      <Input id="archive-date-to" type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />
                    </div>
                  </div>
                  <label className="flex items-center gap-3 rounded-2xl border border-border/70 px-3 py-3 text-sm">
                    <Checkbox checked={presentOnly} onCheckedChange={(checked) => setPresentOnly(checked === true)} />
                    <span>{t("archive.presentOnlyLabel")}</span>
                  </label>
                </div>
              </div>
            </div>
          </Card>

          <section className="grid gap-4">
            {displayedResults.length === 0 ? (
              <Card className="border-border/70 p-8 text-center text-muted-foreground">
                {searchMutation.isPending || initialItemQuery.isPending
                  ? t("archive.searching")
                  : initialItemQuery.isError
                    ? t("archive.itemNotFound")
                    : t("archive.empty")}
              </Card>
            ) : (
              displayedResults.map((item) => {
                const Icon = getContentTypeIcon(item.content_type);
                const archiveItemHref = buildArchiveItemHref(item);
                const telegramOpenHref = buildTelegramOpenHref(item);
                return (
                  <motion.article
                    key={item.corpus_item_id}
                    initial={{ opacity: 0, y: 14 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.22 }}
                  >
                    <Card className="border-border/70 p-5">
                      <div className="flex flex-col gap-5 lg:flex-row">
                        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-border/70 bg-muted/20">
                          <Icon className="h-5 w-5 text-foreground" />
                        </div>
                        <div className="min-w-0 flex-1 space-y-3">
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <div>
                              <p className="text-lg font-semibold">
                                {item.text_preview || item.caption || item.media?.original_filename || t("archive.resultUntitled")}
                              </p>
                              <p className="text-sm text-muted-foreground">
                                {item.source_display_name} · {item.container_name || t("archive.unknownContainer")} · {item.author_name || t("archive.unknownAuthor")} · {new Date(item.occurred_at).toLocaleString()}
                              </p>
                            </div>
                            <span className="rounded-full border border-border/70 px-3 py-1 text-xs uppercase tracking-[0.2em] text-muted-foreground">
                              {item.content_type}
                            </span>
                          </div>

                          {(item.snippet || item.caption || item.text_preview) && (
                            <div className="space-y-2">
                              <div className="flex flex-wrap gap-2">
                                {item.matched_projection_kinds.map((kind) => (
                                  <span
                                    key={`${item.corpus_item_id}-${kind}`}
                                    className="rounded-full border border-border/70 px-2 py-1 text-[11px] uppercase tracking-[0.16em] text-muted-foreground"
                                  >
                                    {kind === "derived_text" ? "Derived" : "Raw"}
                                  </span>
                                ))}
                                {getSnippetBadgeLabel(item.snippet_source) && (
                                  <span className="rounded-full border border-border/70 bg-muted/30 px-2 py-1 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                                    {getSnippetBadgeLabel(item.snippet_source)}
                                  </span>
                                )}
                              </div>
                              <p className="text-sm text-muted-foreground">
                                {item.snippet || item.caption || item.text_preview}
                              </p>
                            </div>
                          )}

                          {item.media?.mime_type?.startsWith("image/") && item.media.play_url && (
                            <img
                              src={item.media.play_url}
                              alt={item.media.original_filename || item.text_preview || "archive-image"}
                              className="max-h-80 rounded-2xl border border-border/70 object-cover"
                            />
                          )}

                          {item.media?.mime_type?.startsWith("audio/") && item.media.play_url && (
                            <audio controls className="w-full" src={item.media.play_url} preload="none" />
                          )}

                          {item.media?.mime_type?.startsWith("video/") && item.media.play_url && (
                            <video controls className="max-h-96 w-full rounded-2xl border border-border/70" src={item.media.play_url} preload="metadata" />
                          )}

                          <div className="flex flex-wrap gap-3">
                            <Button asChild variant="outline">
                              <Link href={archiveItemHref}>
                                <Link2 className="mr-2 h-4 w-4" />
                                {t("archive.openResult")}
                              </Link>
                            </Button>
                            {telegramOpenHref && (
                              <Button asChild variant="outline">
                                <a href={telegramOpenHref}>
                                  <ExternalLink className="mr-2 h-4 w-4" />
                                  {t("archive.openTelegram")}
                                </a>
                              </Button>
                            )}
                            {item.media?.download_url && (
                              <Button asChild variant="outline">
                                <a href={item.media.download_url} target="_blank" rel="noreferrer">
                                  {t("archive.download")}
                                </a>
                              </Button>
                            )}
                            <Button
                              type="button"
                              variant="ghost"
                              onClick={() => similarMutation.mutate({ corpusItemId: item.corpus_item_id })}
                              disabled={similarMutation.isPending}
                            >
                              {similarMutation.isPending ? t("archive.similarLoading") : t("archive.similar")}
                            </Button>
                          </div>
                        </div>
                      </div>
                    </Card>
                  </motion.article>
                );
              })
            )}
          </section>
      </main>
    </div>
  );
}
