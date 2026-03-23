"use client";

import { motion } from "motion/react";
import { LoaderCircle, Shield, Upload } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/app/providers/auth/useAuth";
import { Header } from "@/features/navigation/ui/Header";
import { getBrowserLoginStatus, startBrowserLogin } from "@/shared/api/auth";
import { listAdminClips } from "@/shared/api/clips";
import { listAdminUsers, listUploaderInvites } from "@/shared/api/admin";
import { getTelegramInitData, isTelegramMiniApp, prepareTelegramWebApp } from "@/shared/lib/telegram";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Card } from "@/shared/components/ui/card";
import { useI18n } from "@/shared/i18n/I18nProvider";
import { useEffect, useState } from "react";

export default function AdminPage() {
  const auth = useAuth();
  const { t } = useI18n();
  const [browserLink, setBrowserLink] = useState<string | null>(null);
  const [browserMessage, setBrowserMessage] = useState<string | null>(null);

  useEffect(() => {
    prepareTelegramWebApp();
  }, []);

  const roles = auth?.user?.role_slugs ?? auth?.user?.roles ?? [];
  const isAdmin = roles.includes("admin");
  const canUpload = isAdmin || roles.includes("uploader");

  const clipsQuery = useQuery({
    queryKey: ["admin-clips"],
    queryFn: listAdminClips,
    enabled: canUpload,
  });

  const usersQuery = useQuery({
    queryKey: ["admin-users"],
    queryFn: listAdminUsers,
    enabled: isAdmin,
  });

  const invitesQuery = useQuery({
    queryKey: ["admin-uploader-invites"],
    queryFn: listUploaderInvites,
    enabled: isAdmin,
  });

  if (!auth) {
    throw new Error("Auth context is unavailable. Wrap routes with <AuthProvider>.");
  }

  const handleStartBrowserLogin = async () => {
    try {
      const payload = await startBrowserLogin();
      setBrowserLink(payload.telegram_deep_link);
      const status = await getBrowserLoginStatus(payload.challenge_token);
      if (status.status === "approved") {
        setBrowserMessage(t("auth.approvedFinalizing"));
      } else {
        setBrowserMessage(t("auth.browserStep2"));
      }
    } catch {
      setBrowserMessage(t("auth.startFailed"));
    }
  };

  if (!auth.user) {
    const initData = getTelegramInitData();
    const launchedInsideTelegram = isTelegramMiniApp();

    return (
      <div className="min-h-screen bg-background">
        <Header />
        <main className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-5xl items-center px-4 py-12">
          <Card className="w-full border-border/60 p-8">
            <div className="mx-auto max-w-3xl text-center">
              <p className="text-sm font-semibold uppercase tracking-[0.28em] text-muted-foreground">{t("auth.eyebrow")}</p>
              <h1 className="mt-3 text-3xl font-black tracking-tight sm:text-4xl">{t("auth.title")}</h1>
              <p className="mt-3 text-muted-foreground">{t("auth.subtitle")}</p>

              {launchedInsideTelegram ? (
                <motion.div
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25 }}
                  className="mt-8 rounded-[28px] border border-border/70 bg-muted/20 p-8"
                >
                  <p className="text-sm font-semibold uppercase tracking-[0.28em] text-muted-foreground">{t("auth.miniAppEyebrow")}</p>
                  <h2 className="mt-3 text-2xl font-black tracking-tight">{t("auth.miniAppTitle")}</h2>
                  <p className="mt-3 text-muted-foreground">{t("auth.miniAppBody")}</p>
                  <Button
                    className="mt-6"
                    onClick={() => initData && void auth.authenticateTelegram(initData)}
                    disabled={auth.isAuthenticatingTelegram || !initData}
                  >
                    {auth.isAuthenticatingTelegram ? t("auth.authenticating") : t("auth.continueTelegram")}
                  </Button>
                </motion.div>
              ) : (
                <motion.div
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25 }}
                  className="mt-8 rounded-[28px] border border-border/70 bg-muted/20 p-8"
                >
                  <p className="text-sm font-semibold uppercase tracking-[0.28em] text-muted-foreground">{t("auth.browserEyebrow")}</p>
                  <h2 className="mt-3 text-2xl font-black tracking-tight">{t("auth.browserTitle")}</h2>
                  <p className="mt-3 text-muted-foreground">{t("auth.browserStep1")}</p>
                  <Button className="mt-6" onClick={() => void handleStartBrowserLogin()}>
                    {t("auth.continueBot")}
                  </Button>
                  {browserLink && <p className="mt-4 break-all text-sm text-muted-foreground">{browserLink}</p>}
                  {browserMessage && <p className="mt-3 text-sm text-muted-foreground">{browserMessage}</p>}
                </motion.div>
              )}
            </div>
          </Card>
        </main>
      </div>
    );
  }

  if (!canUpload) {
    return (
      <div className="min-h-screen bg-background">
        <Header />
        <main className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-3xl items-center px-4 py-12">
          <Card className="w-full border-border/60 p-8 text-center">
            <h1 className="text-2xl font-black tracking-tight">{t("auth.accessDeniedTitle")}</h1>
            <p className="mt-3 text-muted-foreground">{t("auth.accessDeniedBody")}</p>
          </Card>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-8 lg:px-6">
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="rounded-[28px] border border-border/60 bg-[linear-gradient(135deg,rgba(17,17,17,0.04),rgba(17,17,17,0.01))] p-6"
        >
          <p className="text-sm font-semibold uppercase tracking-[0.35em] text-muted-foreground">{t("admin.pageEyebrow")}</p>
          <h1 className="mt-3 text-4xl font-black tracking-tight">{t("admin.pageTitle")}</h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-muted-foreground">{t("admin.pageBody")}</p>
        </motion.section>

        <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
          <Card className="border-border/60 p-6">
            <div className="flex items-center gap-3">
              <div className="rounded-2xl bg-foreground p-3 text-background">
                <Upload className="size-5" />
              </div>
              <div>
                <h2 className="text-2xl font-semibold tracking-tight">{t("admin.uploadQueueTitle")}</h2>
                <p className="text-sm text-muted-foreground">{t("admin.uploadQueueBody")}</p>
              </div>
            </div>
            <div className="mt-6 rounded-[28px] border border-dashed border-border/60 bg-muted/20 px-6 py-12 text-center">
              <p className="text-lg font-semibold">{t("admin.dropTitle")}</p>
              <p className="mt-2 text-sm text-muted-foreground">{t("admin.dropBody")}</p>
            </div>
            <div className="mt-6 rounded-2xl border border-border/60 bg-background p-4">
              <p className="font-semibold">{t("admin.uploadedClips")}</p>
              <p className="mt-2 text-sm text-muted-foreground">
                {clipsQuery.data ? `${clipsQuery.data.length} ${t("admin.queueCountSuffix")}` : t("admin.refreshing")}
              </p>
            </div>
          </Card>

          <Card className="border-border/60 p-6">
            <div className="flex items-center gap-3">
              <div className="rounded-2xl bg-foreground p-3 text-background">
                <Shield className="size-5" />
              </div>
              <div>
                <h2 className="text-2xl font-semibold tracking-tight">{t("admin.uploadersAdmins")}</h2>
                <p className="text-sm text-muted-foreground">{t("admin.uploadersAdminsBody")}</p>
              </div>
            </div>
            <div className="mt-6 space-y-4">
              <div className="rounded-2xl border border-border/60 bg-background p-4">
                <p className="font-semibold">{t("admin.inviteUploaderTitle")}</p>
                <p className="mt-2 text-sm text-muted-foreground">{t("admin.inviteUploaderBody")}</p>
              </div>
              <div className="rounded-2xl border border-border/60 bg-background p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="font-semibold">{t("admin.activeInvites")}</p>
                    <p className="mt-2 text-sm text-muted-foreground">{t("admin.activeInvitesBody")}</p>
                  </div>
                  {invitesQuery.isFetching && <LoaderCircle className="size-4 animate-spin text-muted-foreground" />}
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <Badge variant="outline">{usersQuery.data?.length ?? 0} users</Badge>
                  <Badge variant="outline">{invitesQuery.data?.length ?? 0} invites</Badge>
                </div>
              </div>
            </div>
          </Card>
        </div>
      </main>
    </div>
  );
}
