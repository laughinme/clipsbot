"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { useMutation } from "@tanstack/react-query";
import { Copy, ExternalLink, LoaderCircle, Smartphone } from "lucide-react";
import { motion } from "motion/react";
import { toast } from "sonner";

import { useAuth } from "@/app/providers/auth/useAuth";
import { getBrowserLoginStatus, startBrowserLogin } from "@/shared/api/auth";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Card } from "@/shared/components/ui/card";
import { getTelegramInitData, isTelegramMiniApp, prepareTelegramWebApp } from "@/shared/lib/telegram";
import { useI18n } from "@/shared/i18n/I18nProvider";

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

    if ("message" in error) {
      const message = (error as { message?: unknown }).message;
      if (typeof message === "string" && message.trim()) {
        return message;
      }
    }
  }

  return fallback;
};

type AdminAccessGateProps = {
  requiredRoles: string[];
  children: ReactNode;
  accessDeniedTitle: string;
  accessDeniedBody: string;
};

export function AdminAccessGate({
  requiredRoles,
  children,
  accessDeniedTitle,
  accessDeniedBody,
}: AdminAccessGateProps) {
  const auth = useAuth();
  const { t } = useI18n();
  if (!auth) {
    throw new Error("Auth context is unavailable. Wrap pages with <AuthProvider>.");
  }
  const [browserChallenge, setBrowserChallenge] = useState<Awaited<ReturnType<typeof startBrowserLogin>> | null>(null);
  const [browserChallengeStatus, setBrowserChallengeStatus] =
    useState<Awaited<ReturnType<typeof getBrowserLoginStatus>> | null>(null);
  const [browserAuthMessage, setBrowserAuthMessage] = useState<string | null>(null);
  const [isCopyingBrowserLink, setIsCopyingBrowserLink] = useState(false);
  const completingBrowserLoginRef = useRef(false);

  const roles = auth?.user?.role_slugs ?? auth?.user?.roles ?? [];
  const isAllowed = auth?.user ? requiredRoles.some((role) => roles.includes(role)) : false;

  const browserStartMutation = useMutation({
    mutationFn: startBrowserLogin,
    onSuccess: (payload) => {
      setBrowserChallenge(payload);
      setBrowserChallengeStatus({
        challenge_token: payload.challenge_token,
        status: payload.status,
        expires_at: payload.expires_at,
      });
      setBrowserAuthMessage(null);
      completingBrowserLoginRef.current = false;
    },
    onError: (error) => {
      setBrowserAuthMessage(getErrorMessage(error, t("auth.startFailed")));
    },
  });

  useEffect(() => {
    prepareTelegramWebApp();
  }, []);

  useEffect(() => {
    if (auth?.user) {
      setBrowserChallenge(null);
      setBrowserChallengeStatus(null);
      setBrowserAuthMessage(null);
      completingBrowserLoginRef.current = false;
    }
  }, [auth?.user]);

  useEffect(() => {
    if (!browserChallenge || auth?.user) {
      return;
    }

    let cancelled = false;

    const syncBrowserChallenge = async () => {
      try {
        const status = await getBrowserLoginStatus(browserChallenge.challenge_token);
        if (cancelled) {
          return;
        }

        setBrowserChallengeStatus(status);

        if (
          status.status === "approved" &&
          !completingBrowserLoginRef.current &&
          !auth.isCompletingBrowserLogin
        ) {
          completingBrowserLoginRef.current = true;
          setBrowserAuthMessage(t("auth.approvedFinalizing"));
          try {
            await auth.completeBrowserLogin(status.challenge_token);
          } catch (error) {
            completingBrowserLoginRef.current = false;
            setBrowserAuthMessage(getErrorMessage(error, t("auth.completeFailed")));
          }
          return;
        }

        if (status.status === "expired") {
          setBrowserAuthMessage(t("auth.expired"));
        }
      } catch (error) {
        if (!cancelled) {
          setBrowserAuthMessage(getErrorMessage(error, t("auth.refreshFailed")));
        }
      }
    };

    void syncBrowserChallenge();
    const interval = window.setInterval(() => {
      void syncBrowserChallenge();
    }, 2000);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [auth, browserChallenge, t]);

  const handleStartBrowserLogin = async () => {
    setBrowserAuthMessage(null);
    await browserStartMutation.mutateAsync();
  };

  const handleCopyBrowserLink = async () => {
    if (!browserChallenge?.telegram_deep_link || typeof navigator === "undefined" || !navigator.clipboard) {
      toast.error(t("auth.clipboardUnavailable"));
      return;
    }

    setIsCopyingBrowserLink(true);
    try {
      await navigator.clipboard.writeText(browserChallenge.telegram_deep_link);
      toast.success(t("auth.copied"));
    } catch {
      toast.error(t("auth.copyFailed"));
    } finally {
      setIsCopyingBrowserLink(false);
    }
  };

  if (auth?.user && isAllowed) {
    return <>{children}</>;
  }

  if (!auth?.user) {
    const initData = getTelegramInitData();
    const launchedInsideTelegram = isTelegramMiniApp();
    const currentBrowserStatus = browserChallengeStatus?.status ?? browserChallenge?.status ?? null;

    return (
      <main className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-6xl items-center px-4 py-12">
        <Card className="w-full border-border/60 p-8">
          <div className="mx-auto flex max-w-5xl flex-col gap-8">
            <div className="text-center">
              <p className="text-sm font-semibold uppercase tracking-[0.28em] text-muted-foreground">{t("auth.eyebrow")}</p>
              <h1 className="mt-3 text-3xl font-black tracking-tight sm:text-4xl">{t("auth.title")}</h1>
              <p className="mt-3 text-muted-foreground">{t("auth.subtitle")}</p>
            </div>

            {launchedInsideTelegram ? (
              <motion.div
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25 }}
                className="mx-auto w-full max-w-2xl rounded-[28px] border border-border/70 bg-[linear-gradient(145deg,rgba(17,17,17,0.03),rgba(17,17,17,0.01))] p-8 text-center"
              >
                <p className="text-sm font-semibold uppercase tracking-[0.28em] text-muted-foreground">{t("auth.miniAppEyebrow")}</p>
                <h2 className="mt-3 text-2xl font-black tracking-tight">{t("auth.miniAppTitle")}</h2>
                <p className="mt-3 text-muted-foreground">{t("auth.miniAppBody")}</p>
                <Button
                  className="mt-6"
                  onClick={() => initData && void auth.authenticateTelegram(initData)}
                  disabled={auth.isAuthenticatingTelegram || !initData}
                >
                  {auth.isAuthenticatingTelegram
                    ? t("auth.authenticating")
                    : initData
                      ? t("auth.continueTelegram")
                      : t("auth.waitingTelegram")}
                </Button>
                {!initData && (
                  <p className="mt-4 text-sm text-muted-foreground">{t("auth.telegramMissing")}</p>
                )}
              </motion.div>
            ) : (
              <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
                <motion.section
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3 }}
                  className="rounded-[28px] border border-border/70 bg-[linear-gradient(145deg,rgba(17,17,17,0.04),rgba(17,17,17,0.01))] p-6 sm:p-8"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-sm font-semibold uppercase tracking-[0.28em] text-muted-foreground">{t("auth.browserEyebrow")}</p>
                      <h2 className="mt-3 text-2xl font-black tracking-tight">{t("auth.browserTitle")}</h2>
                    </div>
                    <div className="rounded-2xl border border-border/70 bg-background p-3">
                      <Smartphone className="h-5 w-5 text-foreground" />
                    </div>
                  </div>

                  <ol className="mt-6 space-y-3 text-sm text-muted-foreground">
                    <li>{t("auth.browserStep1")}</li>
                    <li>{t("auth.browserStep2")}</li>
                    <li>{t("auth.browserStep3")}</li>
                  </ol>

                  {!browserChallenge ? (
                    <Button
                      className="mt-6"
                      onClick={() => void handleStartBrowserLogin()}
                      disabled={browserStartMutation.isPending}
                    >
                      {browserStartMutation.isPending ? t("auth.creatingLink") : t("auth.continueBot")}
                    </Button>
                  ) : (
                    <div className="mt-6 space-y-4">
                      <div className="rounded-2xl border border-border/70 bg-background p-4">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-muted-foreground">{t("auth.status")}</p>
                            <div className="mt-2 flex flex-wrap items-center gap-2">
                              <Badge
                                variant={
                                  currentBrowserStatus === "approved"
                                    ? "default"
                                    : currentBrowserStatus === "expired"
                                      ? "destructive"
                                      : "secondary"
                                }
                              >
                                {currentBrowserStatus === "approved"
                                  ? t("auth.approvedStatus")
                                  : currentBrowserStatus === "expired"
                                    ? t("auth.expiredStatus")
                                    : t("auth.pendingStatus")}
                              </Badge>
                              {browserChallengeStatus?.approved_display_name && (
                                <span className="text-sm text-muted-foreground">
                                  {browserChallengeStatus.approved_display_name}
                                </span>
                              )}
                            </div>
                          </div>
                          {(browserStartMutation.isPending || auth.isCompletingBrowserLogin) && (
                            <LoaderCircle className="h-5 w-5 animate-spin text-muted-foreground" />
                          )}
                        </div>
                        <p className="mt-3 text-sm text-muted-foreground">
                          {t("auth.expiresAt")} {new Date(browserChallenge.expires_at).toLocaleTimeString()}.
                        </p>
                      </div>

                      <div className="flex flex-wrap gap-3">
                        <Button asChild>
                          <a href={browserChallenge.telegram_deep_link} target="_blank" rel="noreferrer">
                            {t("auth.openTelegram")}
                            <ExternalLink className="ml-2 h-4 w-4" />
                          </a>
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => void handleCopyBrowserLink()}
                          disabled={isCopyingBrowserLink}
                        >
                          <Copy className="mr-2 h-4 w-4" />
                          {isCopyingBrowserLink ? t("auth.copyingLink") : t("auth.copyLink")}
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          onClick={() => void handleStartBrowserLogin()}
                          disabled={browserStartMutation.isPending}
                        >
                          {t("auth.restartLink")}
                        </Button>
                      </div>

                      <div className="rounded-2xl border border-dashed border-border/70 bg-muted/20 p-4 text-sm text-muted-foreground">
                        <p className="font-medium text-foreground">{t("auth.deepLink")}</p>
                        <p className="mt-2 break-all">{browserChallenge.telegram_deep_link}</p>
                      </div>
                    </div>
                  )}
                </motion.section>

                <motion.section
                  initial={{ opacity: 0, y: 22 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.32, delay: 0.05 }}
                  className="rounded-[28px] border border-border/70 bg-background p-6 sm:p-8"
                >
                  <p className="text-sm font-semibold uppercase tracking-[0.28em] text-muted-foreground">{t("auth.browserEyebrow")}</p>
                  <div className="mt-5 space-y-4">
                    <div className="rounded-2xl border border-border/70 p-4">
                      <p className="font-semibold text-foreground">{t("auth.sourceOfTruthTitle")}</p>
                      <p className="mt-2 text-sm text-muted-foreground">{t("auth.sourceOfTruthBody")}</p>
                    </div>
                    <div className="rounded-2xl border border-border/70 p-4">
                      <p className="font-semibold text-foreground">{t("auth.rolesTitle")}</p>
                      <p className="mt-2 text-sm text-muted-foreground">{t("auth.rolesBody")}</p>
                    </div>
                    <div className="rounded-2xl border border-border/70 p-4">
                      <p className="font-semibold text-foreground">{t("auth.openTelegramTitle")}</p>
                      <p className="mt-2 text-sm text-muted-foreground">{t("auth.openTelegramBody")}</p>
                    </div>
                    {browserAuthMessage && (
                      <div className="rounded-2xl border border-border/70 bg-muted/20 p-4 text-sm text-muted-foreground">
                        {browserAuthMessage}
                      </div>
                    )}
                  </div>
                </motion.section>
              </div>
            )}
          </div>
        </Card>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-4xl items-center px-4 py-12">
      <Card className="w-full border-border/60 p-8 text-center">
        <h1 className="text-3xl font-black tracking-tight">{accessDeniedTitle}</h1>
        <p className="mx-auto mt-4 max-w-2xl text-lg text-muted-foreground">{accessDeniedBody}</p>
      </Card>
    </main>
  );
}
