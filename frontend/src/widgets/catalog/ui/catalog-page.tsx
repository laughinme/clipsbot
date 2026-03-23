"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";

import { Header } from "@/features/navigation/ui/Header";
import { listPublicClips } from "@/shared/api/clips";
import { Button } from "@/shared/components/ui/button";
import { Card } from "@/shared/components/ui/card";
import { Input } from "@/shared/components/ui/input";
import { useI18n } from "@/shared/i18n/I18nProvider";

export default function DashboardPage() {
  const { t } = useI18n();
  const [search, setSearch] = React.useState("");
  const { data: clips = [], isLoading } = useQuery({
    queryKey: ["public-clips", search],
    queryFn: () => listPublicClips(search || undefined),
  });

  return (
    <div className="min-h-screen bg-background flex flex-col font-sans">
      <Header />
      <main className="flex-1 w-full max-w-7xl mx-auto px-4 lg:px-6">
        <div className="flex flex-1 flex-col gap-6 py-8">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.25em] text-muted-foreground">
                {t("catalog.eyebrow")}
              </p>
              <h1 className="text-3xl font-black tracking-tight">{t("catalog.title")}</h1>
            </div>
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t("catalog.searchPlaceholder")}
              className="sm:max-w-sm"
            />
          </div>

          {isLoading && <p className="text-muted-foreground">{t("catalog.loading")}</p>}

          {!isLoading && clips.length === 0 && <p className="text-muted-foreground">{t("catalog.empty")}</p>}

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {clips.map((clip) => (
              <Card key={clip.id} className="border-border/60 p-5">
                <div className="space-y-4">
                  <div>
                    <h2 className="text-xl font-semibold">{clip.title}</h2>
                    {clip.description && (
                      <p className="mt-1 text-sm text-muted-foreground">{clip.description}</p>
                    )}
                  </div>
                  {clip.audio_url && (
                    <audio controls preload="none" className="w-full">
                      <source src={clip.audio_url} type="audio/mpeg" />
                    </audio>
                  )}
                  <div className="flex items-center justify-between">
                    <span className="text-xs uppercase tracking-wider text-muted-foreground">
                      {clip.duration_ms ? `${Math.round(clip.duration_ms / 1000)}${t("catalog.secondsShort")}` : clip.status}
                    </span>
                    {clip.download_url && (
                      <Button asChild variant="outline" size="sm">
                        <a href={clip.download_url}>{t("catalog.download")}</a>
                      </Button>
                    )}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
