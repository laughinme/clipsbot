"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { Header } from "@/features/navigation/ui/Header";
import { listPublicClips } from "@/shared/api/clips";
import { Button } from "@/shared/components/ui/button";
import { Card } from "@/shared/components/ui/card";
import { useI18n } from "@/shared/i18n/I18nProvider";

export default function HomePage() {
  const { t } = useI18n();
  const { data: clips = [] } = useQuery({
    queryKey: ["public-clips", "featured"],
    queryFn: () => listPublicClips(),
  });

  return (
    <div className="min-h-screen bg-background flex flex-col font-sans">
      <Header />
      <main className="flex-1">
        <section className="mx-auto flex w-full max-w-7xl flex-col gap-10 px-4 py-16 lg:px-6">
          <div className="grid gap-10 lg:grid-cols-[1.15fr_0.85fr] lg:items-center">
            <div className="space-y-6">
              <p className="text-sm font-semibold uppercase tracking-[0.25em] text-muted-foreground">
                {t("home.eyebrow")}
              </p>
              <h1 className="max-w-3xl text-4xl font-black tracking-tight text-foreground sm:text-6xl">
                {t("home.title")}
              </h1>
              <p className="max-w-2xl text-lg text-muted-foreground">
                {t("home.subtitle")}
              </p>
              <div className="flex flex-wrap gap-3">
                <Button asChild size="lg">
                  <Link href="/catalog">{t("home.openCatalog")}</Link>
                </Button>
                <Button asChild size="lg" variant="outline">
                  <Link href="/archive">{t("home.openArchive")}</Link>
                </Button>
                <Button asChild size="lg" variant="outline">
                  <Link href="/admin">{t("home.openAdmin")}</Link>
                </Button>
              </div>
            </div>
            <div className="grid gap-4">
              <Card className="border-border/60 bg-card/80 p-6 shadow-sm">
                <p className="mb-2 text-sm font-semibold text-muted-foreground">{t("home.archiveCardEyebrow")}</p>
                <h2 className="text-2xl font-black tracking-tight">{t("home.archiveCardTitle")}</h2>
                <p className="mt-3 text-sm text-muted-foreground">{t("home.archiveCardBody")}</p>
              </Card>
              <Card className="border-border/60 bg-card/80 p-6 shadow-sm">
                <p className="mb-4 text-sm font-semibold text-muted-foreground">{t("home.latestClips")}</p>
                <div className="space-y-4">
                  {clips.slice(0, 5).map((clip) => (
                    <div key={clip.id} className="rounded-lg border border-border/60 p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="font-semibold">{clip.title}</p>
                          {clip.description && (
                            <p className="mt-1 text-sm text-muted-foreground">{clip.description}</p>
                          )}
                        </div>
                        <span className="text-xs uppercase text-muted-foreground">{clip.status}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
