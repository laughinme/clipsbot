"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  CheckCircle2,
  Copy,
  ExternalLink,
  FolderOpen,
  LoaderCircle,
  Music4,
  PencilLine,
  Sparkles,
  Smartphone,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/app/providers/auth/useAuth";
import { Header } from "@/features/navigation/ui/Header";
import { getBrowserLoginStatus, startBrowserLogin } from "@/shared/api/auth";
import {
  deleteClip,
  finalizeClipUpload,
  initClipUpload,
  listAdminClips,
  updateClip,
  uploadClipObject,
  type ClipDto,
} from "@/shared/api/clips";
import {
  createUploaderInvite,
  listAdminUsers,
  listUploaderInvites,
  revokeUploaderInvite,
  setUserRoles,
  type UploaderInviteDto,
} from "@/shared/api/admin";
import { getTelegramInitData, isTelegramMiniApp, prepareTelegramWebApp } from "@/shared/lib/telegram";
import { cn } from "@/shared/lib/utils";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Card } from "@/shared/components/ui/card";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Separator } from "@/shared/components/ui/separator";
import { useI18n } from "@/shared/i18n/I18nProvider";

const ALLOWED_CLIP_EXTENSIONS = new Set(["mp3", "ogg", "opus", "wav", "m4a", "aac", "flac", "webm"]);
const ALLOWED_CLIP_MIME_TYPES = new Set([
  "audio/mpeg",
  "audio/mp3",
  "audio/x-mpeg",
  "audio/x-mp3",
  "audio/ogg",
  "application/ogg",
  "audio/opus",
  "audio/wav",
  "audio/wave",
  "audio/x-wav",
  "audio/aac",
  "audio/x-aac",
  "audio/mp4",
  "audio/x-m4a",
  "audio/flac",
  "audio/x-flac",
  "audio/webm",
  "application/octet-stream",
]);

type QueueItemStatus = "queued" | "uploading" | "processing" | "ready" | "failed";

type UploadQueueItem = {
  id: string;
  file: File;
  title: string;
  description: string;
  aliasesInput: string;
  isPublic: boolean;
  progress: number;
  status: QueueItemStatus;
  error?: string;
  serverClipId?: string;
  objectKey?: string | null;
};

const statusBadgeVariant: Record<QueueItemStatus, "secondary" | "outline" | "default" | "destructive"> = {
  queued: "outline",
  uploading: "secondary",
  processing: "secondary",
  ready: "default",
  failed: "destructive",
};

const getStatusLabels = (t: (path: string, values?: Record<string, string | number>) => string): Record<QueueItemStatus, string> => ({
  queued: t("admin.queuedStatus"),
  uploading: t("admin.uploadingStatus"),
  processing: t("admin.processingStatus"),
  ready: t("admin.readyStatus"),
  failed: t("admin.failedStatus"),
});

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (typeof error === "object" && error !== null) {
    const response = "response" in error ? (error as { response?: { data?: unknown } }).response : undefined;
    const data = response?.data;

    if (typeof data === "object" && data !== null) {
      const detail = "detail" in data ? (data as { detail?: unknown }).detail : undefined;
      if (typeof detail === "string" && detail.trim()) {
        return detail;
      }
    }

    const message = "message" in error ? (error as { message?: unknown }).message : undefined;
    if (typeof message === "string" && message.trim()) {
      return message;
    }
  }

  return fallback;
};

const isSupportedClipFile = (file: File): boolean => {
  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  return (
    ALLOWED_CLIP_EXTENSIONS.has(extension) ||
    ALLOWED_CLIP_MIME_TYPES.has(file.type) ||
    file.type.startsWith("audio/")
  );
};

const createLocalId = (): string => {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `queue-${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

const titleFromFileName = (filename: string): string => {
  return filename.replace(/\.[^.]+$/, "").trim() || filename;
};

const formatBytes = (bytes: number): string => {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB"];
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** exponent;
  return `${value >= 10 || exponent === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[exponent]}`;
};

const formatDuration = (durationMs?: number | null): string => {
  if (!durationMs || durationMs <= 0) {
    return "0:00";
  }
  const totalSeconds = Math.round(durationMs / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
};

const toAliases = (value: string): string[] => {
  return value.split(",").map((alias) => alias.trim()).filter(Boolean);
};

const makeQueueItem = (file: File): UploadQueueItem => ({
  id: createLocalId(),
  file,
  title: titleFromFileName(file.name),
  description: "",
  aliasesInput: "",
  isPublic: true,
  progress: 0,
  status: "queued",
});

export default function AdminPage() {
  const auth = useAuth();
  const { t } = useI18n();
  if (!auth) {
    throw new Error("Auth context is unavailable. Wrap routes with <AuthProvider>.");
  }

  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const folderInputRef = useRef<HTMLInputElement | null>(null);
  const queueRef = useRef<UploadQueueItem[]>([]);
  const completingBrowserLoginRef = useRef(false);

  const [queue, setQueue] = useState<UploadQueueItem[]>([]);
  const [selectedQueueId, setSelectedQueueId] = useState<string | null>(null);
  const [isDragActive, setIsDragActive] = useState(false);
  const [isUploadingAll, setIsUploadingAll] = useState(false);
  const [browserChallenge, setBrowserChallenge] = useState<Awaited<ReturnType<typeof startBrowserLogin>> | null>(null);
  const [browserChallengeStatus, setBrowserChallengeStatus] = useState<Awaited<ReturnType<typeof getBrowserLoginStatus>> | null>(null);
  const [browserAuthMessage, setBrowserAuthMessage] = useState<string | null>(null);
  const [isCopyingBrowserLink, setIsCopyingBrowserLink] = useState(false);
  const [latestInvite, setLatestInvite] = useState<UploaderInviteDto | null>(null);
  const [copyingInviteId, setCopyingInviteId] = useState<string | null>(null);

  queueRef.current = queue;

  const roles = useMemo(() => auth.user?.role_slugs ?? auth.user?.roles ?? [], [auth.user]);
  const canUpload = roles.includes("admin") || roles.includes("uploader");
  const isAdmin = roles.includes("admin");
  const hasActiveQueue = queue.some((item) => item.status === "uploading" || item.status === "processing");
  const queuedCount = queue.filter((item) => item.status === "queued").length;
  const processingCount = queue.filter((item) => item.status === "uploading" || item.status === "processing").length;
  const completedCount = queue.filter((item) => item.status === "ready").length;
  const statusLabel = useMemo(() => getStatusLabels(t), [t]);

  const clipsQuery = useQuery({
    queryKey: ["admin-clips"],
    queryFn: listAdminClips,
    enabled: canUpload,
    refetchInterval: canUpload && hasActiveQueue ? 2500 : false,
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

  const deleteMutation = useMutation({
    mutationFn: deleteClip,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-clips"] });
      toast.success(t("admin.deleteSuccess"));
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, t("admin.deleteFailed")));
    },
  });

  const publishMutation = useMutation({
    mutationFn: ({ clipId, nextPublic }: { clipId: string; nextPublic: boolean }) =>
      updateClip(clipId, { is_public: nextPublic }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-clips"] });
      toast.success(t("admin.visibilityUpdated"));
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, t("admin.visibilityFailed")));
    },
  });

  const roleMutation = useMutation({
    mutationFn: ({ userId, nextRoles }: { userId: string; nextRoles: string[] }) => setUserRoles(userId, nextRoles),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  const createInviteMutation = useMutation({
    mutationFn: createUploaderInvite,
    onSuccess: async (invite) => {
      setLatestInvite(invite);
      await queryClient.invalidateQueries({ queryKey: ["admin-uploader-invites"] });
      toast.success(t("admin.inviteCreated"));
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, t("admin.inviteCreateFailed")));
    },
  });

  const revokeInviteMutation = useMutation({
    mutationFn: revokeUploaderInvite,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-uploader-invites"] });
      toast.success(t("admin.inviteRevokedSuccess"));
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, t("admin.inviteRevokeFailed")));
    },
  });

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
    if (!folderInputRef.current) {
      return;
    }

    folderInputRef.current.setAttribute("webkitdirectory", "");
    folderInputRef.current.setAttribute("directory", "");
  }, []);

  useEffect(() => {
    if (!queue.length) {
      setSelectedQueueId(null);
      return;
    }

    if (!selectedQueueId || !queue.some((item) => item.id === selectedQueueId)) {
      setSelectedQueueId(queue[0]?.id ?? null);
    }
  }, [queue, selectedQueueId]);

  useEffect(() => {
    if (auth.user) {
      setBrowserChallenge(null);
      setBrowserChallengeStatus(null);
      setBrowserAuthMessage(null);
      completingBrowserLoginRef.current = false;
    }
  }, [auth.user]);

  useEffect(() => {
    if (!latestInvite && invitesQuery.data?.length) {
      setLatestInvite(invitesQuery.data[0] ?? null);
    }
  }, [invitesQuery.data, latestInvite]);

  useEffect(() => {
    if (!browserChallenge || auth.user) {
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

  useEffect(() => {
    if (!clipsQuery.data?.length) {
      return;
    }

    setQueue((current) =>
      current.map((item) => {
        if (!item.serverClipId) {
          return item;
        }

        const clip = clipsQuery.data.find((candidate) => candidate.id === item.serverClipId);
        if (!clip) {
          return item;
        }

        const nextStatus = clip.status === "uploading" ? "uploading" : clip.status;
        return {
          ...item,
          status: nextStatus,
          progress: nextStatus === "ready" ? 100 : item.progress,
          error: nextStatus === "failed" ? item.error ?? t("admin.processingFailed") : undefined,
        };
      }),
    );
  }, [clipsQuery.data, t]);

  const selectedQueueItem = queue.find((item) => item.id === selectedQueueId) ?? null;
  const currentBrowserStatus = browserChallengeStatus?.status ?? browserChallenge?.status ?? null;

  const patchQueueItem = (itemId: string, patch: Partial<UploadQueueItem>) => {
    setQueue((current) => current.map((item) => (item.id === itemId ? { ...item, ...patch } : item)));
  };

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

  const handleCreateInvite = async () => {
    await createInviteMutation.mutateAsync();
  };

  const handleCopyInvite = async (invite: UploaderInviteDto) => {
    if (typeof navigator === "undefined" || !navigator.clipboard) {
      toast.error(t("auth.clipboardUnavailable"));
      return;
    }

    setCopyingInviteId(invite.id);
    try {
      await navigator.clipboard.writeText(invite.invite_link);
      toast.success(t("admin.copiedInvite"));
    } catch {
      toast.error(t("admin.copyInviteFailed"));
    } finally {
      setCopyingInviteId(null);
    }
  };

  const addFiles = (files: FileList | File[]) => {
    const normalized = Array.from(files);
    if (!normalized.length) {
      return;
    }

    const supported: UploadQueueItem[] = [];
    let rejected = 0;

    normalized.forEach((file) => {
      if (!isSupportedClipFile(file)) {
        rejected += 1;
        return;
      }
      supported.push(makeQueueItem(file));
    });

    if (!supported.length) {
      toast.error(t("admin.noSupportedFiles"));
      return;
    }

    setQueue((current) => [...supported, ...current]);
    setSelectedQueueId((current) => current ?? supported[0]?.id ?? null);

    if (rejected > 0) {
      toast.error(t("admin.skippedUnsupported", { count: rejected }));
    } else {
      toast.success(t("admin.addedToQueue", { count: supported.length }));
    }
  };

  const removeQueueItem = (itemId: string) => {
    setQueue((current) => current.filter((item) => item.id !== itemId));
  };

  const clearCompleted = () => {
    setQueue((current) => current.filter((item) => item.status !== "ready"));
  };

  const uploadQueueItem = async (itemId: string): Promise<void> => {
    const current = queueRef.current.find((item) => item.id === itemId);
    if (!current || current.status === "uploading" || current.status === "processing" || current.status === "ready") {
      return;
    }

    if (!current.title.trim()) {
      patchQueueItem(itemId, { status: "failed", error: t("admin.titleRequired") });
      return;
    }

    patchQueueItem(itemId, { status: "uploading", progress: 0, error: undefined });

    try {
      const init = await initClipUpload({
        title: current.title.trim(),
        description: current.description.trim() || undefined,
        is_public: current.isPublic,
        aliases: toAliases(current.aliasesInput),
        filename: current.file.name,
        content_type: current.file.type || "application/octet-stream",
      });

      patchQueueItem(itemId, {
        serverClipId: init.clip.id,
        objectKey: init.clip.object_key ?? null,
      });

      await uploadClipObject(init.upload_url, current.file, (progress) => {
        patchQueueItem(itemId, { progress, status: "uploading" });
      });

      const clip = await finalizeClipUpload(init.clip.id, init.clip.object_key ?? "");
      patchQueueItem(itemId, {
        serverClipId: clip.id,
        objectKey: clip.object_key ?? null,
        progress: 100,
        status: clip.status === "ready" ? "ready" : clip.status,
        error: clip.status === "failed" ? t("admin.processingFailed") : undefined,
      });
      queryClient.invalidateQueries({ queryKey: ["admin-clips"] });
    } catch (error) {
      patchQueueItem(itemId, {
        status: "failed",
        error: getErrorMessage(error, t("admin.uploadFailed")),
      });
    }
  };

  const uploadAll = async () => {
    const items = queueRef.current.filter((item) => item.status === "queued" || item.status === "failed");
    if (!items.length) {
      toast.error(t("admin.noFilesToUpload"));
      return;
    }

    setIsUploadingAll(true);
    for (const item of items) {
      // Sequential uploads keep the UI predictable and make retries easier to understand.
      await uploadQueueItem(item.id);
    }
    setIsUploadingAll(false);
    queryClient.invalidateQueries({ queryKey: ["admin-clips"] });
    toast.success(t("admin.queueFinished"));
  };

  if (!auth.user) {
    const initData = getTelegramInitData();
    const launchedInsideTelegram = isTelegramMiniApp();

    return (
      <div className="min-h-screen bg-background">
        <Header />
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
      <main className="mx-auto flex w-full max-w-7xl flex-col gap-8 px-4 py-8 lg:px-6">
        <motion.section
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
          className="relative overflow-hidden rounded-[28px] border border-border/60 bg-[linear-gradient(135deg,rgba(17,17,17,0.04),rgba(17,17,17,0.01))] p-6 shadow-sm"
        >
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(0,0,0,0.08),transparent_40%)]" />
          <div className="relative flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-sm font-semibold uppercase tracking-[0.35em] text-muted-foreground">{t("admin.pageEyebrow")}</p>
              <h1 className="mt-3 text-4xl font-black tracking-tight text-foreground sm:text-5xl">
                {t("admin.pageTitle")}
              </h1>
              <p className="mt-4 max-w-2xl text-base leading-7 text-muted-foreground">{t("admin.pageBody")}</p>
            </div>
            <div className="grid grid-cols-3 gap-3 sm:w-auto">
              {[
                { label: t("admin.queued"), value: queuedCount },
                { label: t("admin.inFlight"), value: processingCount },
                { label: t("admin.ready"), value: completedCount },
              ].map((stat) => (
                <div key={stat.label} className="rounded-2xl border border-border/50 bg-background/85 px-4 py-3 text-center backdrop-blur">
                  <p className="text-2xl font-black">{stat.value}</p>
                  <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">{stat.label}</p>
                </div>
              ))}
            </div>
          </div>
        </motion.section>

        <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
          <Card className="overflow-hidden border-border/60 p-0">
            <div className="border-b border-border/60 px-6 py-5">
              <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
                <div className="max-w-2xl">
                  <div className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-background px-3 py-1 text-xs uppercase tracking-[0.2em] text-muted-foreground">
                    <Sparkles className="size-3.5" />
                    {t("admin.uploadQueueEyebrow")}
                  </div>
                  <h2 className="mt-4 text-2xl font-semibold tracking-tight">{t("admin.uploadQueueTitle")}</h2>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">{t("admin.uploadQueueBody")}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button type="button" variant="outline" onClick={() => fileInputRef.current?.click()}>
                    <Upload />
                    {t("admin.addFiles")}
                  </Button>
                  <Button type="button" variant="outline" onClick={() => folderInputRef.current?.click()}>
                    <FolderOpen />
                    {t("admin.addFolder")}
                  </Button>
                  <Button
                    type="button"
                    onClick={() => void uploadAll()}
                    disabled={isUploadingAll || !queue.some((item) => item.status === "queued" || item.status === "failed")}
                  >
                    {isUploadingAll ? (
                      <>
                        <LoaderCircle className="animate-spin" />
                        {t("admin.uploadingAll")}
                      </>
                    ) : (
                      <>
                        <ArrowUploadIcon />
                        {t("admin.uploadAll")}
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </div>

            <div className="px-6 py-6">
              <motion.div
                onDragEnter={(event) => {
                  event.preventDefault();
                  setIsDragActive(true);
                }}
                onDragOver={(event) => {
                  event.preventDefault();
                  setIsDragActive(true);
                }}
                onDragLeave={(event) => {
                  event.preventDefault();
                  if (event.currentTarget.contains(event.relatedTarget as Node | null)) {
                    return;
                  }
                  setIsDragActive(false);
                }}
                onDrop={(event) => {
                  event.preventDefault();
                  setIsDragActive(false);
                  addFiles(event.dataTransfer.files);
                }}
                animate={{
                  scale: isDragActive ? 1.01 : 1,
                  borderColor: isDragActive ? "rgba(17,17,17,0.45)" : "rgba(17,17,17,0.12)",
                  backgroundColor: isDragActive ? "rgba(17,17,17,0.05)" : "rgba(17,17,17,0.02)",
                }}
                transition={{ type: "spring", stiffness: 280, damping: 28 }}
                className="rounded-[28px] border border-dashed px-6 py-10 text-center"
              >
                <motion.div
                  animate={isDragActive ? { y: -4 } : { y: 0 }}
                  transition={{ type: "spring", stiffness: 220, damping: 18 }}
                  className="mx-auto flex max-w-xl flex-col items-center"
                >
                  <div className="flex size-16 items-center justify-center rounded-2xl bg-foreground text-background shadow-sm">
                    <Music4 className="size-7" />
                  </div>
                  <h3 className="mt-5 text-xl font-semibold tracking-tight">{t("admin.dropTitle")}</h3>
                  <p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">{t("admin.dropBody")}</p>
                  <div className="mt-5 flex flex-wrap justify-center gap-2">
                    <Badge variant="outline">MP3</Badge>
                    <Badge variant="outline">OGG / OPUS</Badge>
                    <Badge variant="outline">WAV / M4A</Badge>
                    <Badge variant="outline">AAC / FLAC / WebM</Badge>
                  </div>
                </motion.div>
              </motion.div>

              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                accept=".mp3,.ogg,.opus,.wav,.m4a,.aac,.flac,.webm,audio/*"
                multiple
                onChange={(event) => {
                  if (event.target.files) {
                    addFiles(event.target.files);
                    event.target.value = "";
                  }
                }}
              />
              <input
                ref={folderInputRef}
                type="file"
                className="hidden"
                multiple
                onChange={(event) => {
                  if (event.target.files) {
                    addFiles(event.target.files);
                    event.target.value = "";
                  }
                }}
              />

              <div className="mt-6 flex flex-wrap items-center gap-2">
                <Badge variant="outline">{queue.length} {t("admin.queueCountSuffix")}</Badge>
                <Badge variant="outline">{processingCount} {t("admin.active")}</Badge>
                {queue.some((item) => item.status === "ready") && (
                  <Button type="button" variant="ghost" size="sm" onClick={clearCompleted}>
                    {t("admin.clearCompleted")}
                  </Button>
                )}
              </div>

              <div className="mt-6">
                <AnimatePresence initial={false}>
                  {queue.length === 0 ? (
                    <motion.div
                      key="empty"
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -8 }}
                      className="rounded-2xl border border-border/60 bg-muted/20 px-5 py-10 text-center"
                    >
                      <p className="text-lg font-semibold">{t("admin.queueEmptyTitle")}</p>
                      <p className="mt-2 text-sm text-muted-foreground">{t("admin.queueEmptyBody")}</p>
                    </motion.div>
                  ) : (
                    <motion.div layout className="space-y-3">
                      {queue.map((item, index) => (
                        <motion.button
                          key={item.id}
                          layout
                          initial={{ opacity: 0, y: 18 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -18 }}
                          transition={{ delay: Math.min(index * 0.03, 0.18) }}
                          type="button"
                          onClick={() => setSelectedQueueId(item.id)}
                          className={cn(
                            "w-full rounded-2xl border px-4 py-4 text-left transition-all",
                            item.id === selectedQueueId
                              ? "border-foreground/80 bg-foreground text-background shadow-lg"
                              : "border-border/60 bg-background hover:border-foreground/20 hover:bg-muted/20",
                          )}
                        >
                          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                            <div className="min-w-0 flex-1">
                              <div className="flex flex-wrap items-center gap-2">
                                <p className="truncate text-lg font-semibold">{item.title || titleFromFileName(item.file.name)}</p>
                                <Badge variant={item.id === selectedQueueId ? "secondary" : statusBadgeVariant[item.status]}>
                                  {statusLabel[item.status]}
                                </Badge>
                                <Badge variant={item.id === selectedQueueId ? "secondary" : "outline"}>
                                  {item.isPublic ? t("admin.public") : t("admin.private")}
                                </Badge>
                              </div>
                              <p
                                className={cn(
                                  "mt-1 truncate text-sm",
                                  item.id === selectedQueueId ? "text-background/75" : "text-muted-foreground",
                                )}
                              >
                                {item.file.name}
                              </p>
                              {item.description && (
                                <p
                                  className={cn(
                                    "mt-2 line-clamp-2 text-sm",
                                    item.id === selectedQueueId ? "text-background/80" : "text-muted-foreground",
                                  )}
                                >
                                  {item.description}
                                </p>
                              )}
                              <div className="mt-3 flex flex-wrap gap-3 text-xs uppercase tracking-[0.2em]">
                                <span>{formatBytes(item.file.size)}</span>
                                <span>{item.file.type || t("admin.audioFile")}</span>
                              </div>
                            </div>

                            <div className="flex flex-wrap gap-2">
                              <Button
                                type="button"
                                variant={item.id === selectedQueueId ? "secondary" : "outline"}
                                size="sm"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  setSelectedQueueId(item.id);
                                }}
                              >
                                <PencilLine />
                                {t("admin.edit")}
                              </Button>
                              {(item.status === "queued" || item.status === "failed") && (
                                <Button
                                  type="button"
                                  size="sm"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    void uploadQueueItem(item.id);
                                  }}
                                >
                                  <Upload />
                                  {item.status === "failed" ? t("admin.retry") : t("admin.upload")}
                                </Button>
                              )}
                              <Button
                                type="button"
                                variant={item.id === selectedQueueId ? "secondary" : "ghost"}
                                size="sm"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  removeQueueItem(item.id);
                                }}
                              >
                                <Trash2 />
                                {t("admin.remove")}
                              </Button>
                            </div>
                          </div>

                          <div className="mt-4">
                            <div
                              className={cn(
                                "h-2 overflow-hidden rounded-full",
                                item.id === selectedQueueId ? "bg-background/15" : "bg-muted",
                              )}
                            >
                              <motion.div
                                animate={{ width: `${item.status === "ready" ? 100 : item.progress}%` }}
                                transition={{ type: "spring", stiffness: 220, damping: 28 }}
                                className={cn(
                                  "h-full rounded-full",
                                  item.status === "failed"
                                    ? "bg-destructive"
                                    : item.id === selectedQueueId
                                      ? "bg-background"
                                      : "bg-foreground",
                                )}
                              />
                            </div>
                            {item.error && (
                              <p
                                className={cn(
                                  "mt-2 text-sm",
                                  item.id === selectedQueueId ? "text-background" : "text-destructive",
                                )}
                              >
                                {item.error}
                              </p>
                            )}
                          </div>
                        </motion.button>
                      ))}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>
          </Card>

          <Card className="border-border/60 p-0">
            <div className="border-b border-border/60 px-6 py-5">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h2 className="text-2xl font-semibold tracking-tight">{t("admin.selectedFile")}</h2>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">{t("admin.selectedFileBody")}</p>
                </div>
                {selectedQueueItem && (
                  <Badge variant={statusBadgeVariant[selectedQueueItem.status]}>{statusLabel[selectedQueueItem.status]}</Badge>
                )}
              </div>
            </div>

            <div className="px-6 py-6">
              {selectedQueueItem ? (
                <motion.div
                  key={selectedQueueItem.id}
                  initial={{ opacity: 0, x: 12 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.25 }}
                  className="space-y-5"
                >
                  <div className="rounded-2xl border border-border/60 bg-muted/20 p-4">
                    <p className="text-sm font-semibold">{selectedQueueItem.file.name}</p>
                    <p className="mt-2 text-sm text-muted-foreground">
                      {formatBytes(selectedQueueItem.file.size)} · {selectedQueueItem.file.type || t("admin.audioFile")}
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="queue-title">{t("admin.fileTitle")}</Label>
                    <Input
                      id="queue-title"
                      value={selectedQueueItem.title}
                      onChange={(event) => patchQueueItem(selectedQueueItem.id, { title: event.target.value })}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="queue-description">{t("admin.fileSubtitle")}</Label>
                    <textarea
                      id="queue-description"
                      value={selectedQueueItem.description}
                      onChange={(event) => patchQueueItem(selectedQueueItem.id, { description: event.target.value })}
                      rows={4}
                      className="flex min-h-28 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs transition-[color,box-shadow] outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
                      placeholder={t("admin.fileSubtitlePlaceholder")}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="queue-aliases">{t("admin.aliases")}</Label>
                    <Input
                      id="queue-aliases"
                      value={selectedQueueItem.aliasesInput}
                      onChange={(event) => patchQueueItem(selectedQueueItem.id, { aliasesInput: event.target.value })}
                      placeholder={t("admin.aliasesPlaceholder")}
                    />
                  </div>

                  <label className="flex items-center gap-3 rounded-2xl border border-border/60 px-4 py-3 text-sm">
                    <input
                      type="checkbox"
                      checked={selectedQueueItem.isPublic}
                      onChange={(event) => patchQueueItem(selectedQueueItem.id, { isPublic: event.target.checked })}
                    />
                    {t("admin.visiblePublic")}
                  </label>

                  <Separator />

                  <div className="flex flex-wrap gap-2">
                    {(selectedQueueItem.status === "queued" || selectedQueueItem.status === "failed") && (
                      <Button type="button" onClick={() => void uploadQueueItem(selectedQueueItem.id)}>
                        <Upload />
                        {selectedQueueItem.status === "failed" ? t("admin.retryUpload") : t("admin.uploadThisClip")}
                      </Button>
                    )}
                    <Button type="button" variant="outline" onClick={() => removeQueueItem(selectedQueueItem.id)}>
                      <Trash2 />
                      {t("admin.removeFromQueue")}
                    </Button>
                  </div>
                </motion.div>
              ) : (
                <div className="rounded-2xl border border-dashed border-border/60 px-5 py-12 text-center">
                  <p className="text-lg font-semibold">{t("admin.pickQueuedTitle")}</p>
                  <p className="mt-2 text-sm text-muted-foreground">{t("admin.pickQueuedBody")}</p>
                </div>
              )}
            </div>
          </Card>
        </div>

        <Card className="border-border/60 p-0">
            <div className="border-b border-border/60 px-6 py-5">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="text-2xl font-semibold tracking-tight">{t("admin.uploadedClips")}</h2>
                  <p className="mt-1 text-sm text-muted-foreground">{t("admin.uploadedClipsBody")}</p>
                </div>
              {clipsQuery.isFetching && (
                <div className="inline-flex items-center gap-2 text-sm text-muted-foreground">
                  <LoaderCircle className="size-4 animate-spin" />
                  {t("admin.refreshing")}
                </div>
              )}
            </div>
          </div>

          <div className="px-6 py-6">
            <div className="grid gap-4 lg:grid-cols-2">
              {(clipsQuery.data ?? []).map((clip) => (
                <UploadedClipCard
                  key={clip.id}
                  clip={clip}
                  onTogglePublic={(nextPublic) => publishMutation.mutate({ clipId: clip.id, nextPublic })}
                  onDelete={() => deleteMutation.mutate(clip.id)}
                />
              ))}
            </div>
          </div>
        </Card>

        {isAdmin && (
          <Card className="border-border/60 p-0">
            <div className="border-b border-border/60 px-6 py-5">
              <h2 className="text-2xl font-semibold tracking-tight">{t("admin.uploadersAdmins")}</h2>
              <p className="mt-2 text-sm text-muted-foreground">{t("admin.uploadersAdminsBody")}</p>
            </div>
            <div className="px-6 py-6">
              <motion.div
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25 }}
                className="mb-6 rounded-[28px] border border-border/60 bg-[linear-gradient(140deg,rgba(17,17,17,0.05),rgba(17,17,17,0.01))] p-5"
              >
                <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                  <div className="max-w-2xl">
                    <div className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-background px-3 py-1 text-xs uppercase tracking-[0.2em] text-muted-foreground">
                      <Sparkles className="size-3.5" />
                      {t("admin.inviteUploaderTitle")}
                    </div>
                    <p className="mt-4 text-sm leading-6 text-muted-foreground">{t("admin.inviteUploaderBody")}</p>
                  </div>
                  <Button
                    type="button"
                    onClick={() => void handleCreateInvite()}
                    disabled={createInviteMutation.isPending}
                  >
                    {createInviteMutation.isPending ? (
                      <>
                        <LoaderCircle className="animate-spin" />
                        {t("admin.creatingInvite")}
                      </>
                    ) : (
                      <>
                        <Copy />
                        {t("admin.createInvite")}
                      </>
                    )}
                  </Button>
                </div>

                <AnimatePresence initial={false}>
                  {latestInvite && (
                    <motion.div
                      key={latestInvite.id}
                      initial={{ opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -12 }}
                      className="mt-5 rounded-2xl border border-border/60 bg-background p-4"
                    >
                      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                        <div className="min-w-0">
                          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                            {t("admin.createInvite")}
                          </p>
                          <p className="mt-2 break-all text-sm text-foreground">{latestInvite.invite_link}</p>
                          <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
                            <span>{t("admin.expiresLabel")} {new Date(latestInvite.expires_at).toLocaleString()}</span>
                          </div>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Button
                            type="button"
                            variant="outline"
                            onClick={() => void handleCopyInvite(latestInvite)}
                            disabled={copyingInviteId === latestInvite.id}
                          >
                            <Copy />
                            {copyingInviteId === latestInvite.id ? t("auth.copyingLink") : t("admin.copyInvite")}
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            onClick={() => revokeInviteMutation.mutate(latestInvite.id)}
                            disabled={revokeInviteMutation.isPending}
                          >
                            <X />
                            {t("admin.revokeInvite")}
                          </Button>
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

                <div className="mt-5 rounded-2xl border border-border/60 bg-background/70 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-semibold">{t("admin.activeInvites")}</p>
                      <p className="mt-1 text-sm text-muted-foreground">{t("admin.activeInvitesBody")}</p>
                    </div>
                    {invitesQuery.isFetching && <LoaderCircle className="size-4 animate-spin text-muted-foreground" />}
                  </div>
                  <div className="mt-4 space-y-3">
                    {(invitesQuery.data ?? []).length === 0 ? (
                      <div className="rounded-2xl border border-dashed border-border/60 px-4 py-8 text-center">
                        <p className="font-semibold">{t("admin.noInvitesYet")}</p>
                        <p className="mt-2 text-sm text-muted-foreground">{t("admin.noInvitesYetBody")}</p>
                      </div>
                    ) : (
                      (invitesQuery.data ?? []).map((invite) => {
                        const inviteStatusLabel =
                          invite.status === "consumed"
                            ? t("admin.inviteConsumed")
                            : invite.status === "revoked"
                              ? t("admin.inviteRevoked")
                              : invite.status === "expired"
                                ? t("admin.inviteExpired")
                                : t("admin.invitePending");

                        return (
                          <motion.div
                            key={invite.id}
                            layout
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="rounded-2xl border border-border/60 p-4"
                          >
                            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                              <div className="min-w-0">
                                <div className="flex flex-wrap items-center gap-2">
                                  <Badge
                                    variant={
                                      invite.status === "consumed"
                                        ? "default"
                                        : invite.status === "revoked" || invite.status === "expired"
                                          ? "destructive"
                                          : "secondary"
                                    }
                                  >
                                    {inviteStatusLabel}
                                  </Badge>
                                </div>
                                <p className="mt-3 break-all text-sm text-foreground">{invite.invite_link}</p>
                                <div className="mt-3 flex flex-wrap gap-3 text-xs text-muted-foreground">
                                  <span>{t("admin.createdLabel")} {new Date(invite.created_at).toLocaleString()}</span>
                                  <span>{t("admin.expiresLabel")} {new Date(invite.expires_at).toLocaleString()}</span>
                                </div>
                              </div>
                              <div className="flex flex-wrap gap-2">
                                <Button
                                  type="button"
                                  variant="outline"
                                  onClick={() => void handleCopyInvite(invite)}
                                  disabled={copyingInviteId === invite.id}
                                >
                                  <Copy />
                                  {copyingInviteId === invite.id ? t("auth.copyingLink") : t("admin.copyInvite")}
                                </Button>
                                {invite.status === "pending" && (
                                  <Button
                                    type="button"
                                    variant="ghost"
                                    onClick={() => revokeInviteMutation.mutate(invite.id)}
                                    disabled={revokeInviteMutation.isPending}
                                  >
                                    <X />
                                    {t("admin.revokeInvite")}
                                  </Button>
                                )}
                              </div>
                            </div>
                          </motion.div>
                        );
                      })
                    )}
                  </div>
                </div>
              </motion.div>
              <div className="space-y-4">
                {(usersQuery.data ?? []).map((user) => {
                  const currentRoles = user.role_slugs ?? user.roles ?? [];
                  const isCurrentSessionUser = String(user.id) === String(auth.user?.id);
                  const toggleRole = (role: string) => {
                    if (isCurrentSessionUser) {
                      toast.error(t("admin.selfRoleLockedToast"));
                      return;
                    }
                    const nextRoles = currentRoles.includes(role)
                      ? currentRoles.filter((value) => value !== role)
                      : [...currentRoles, role];
                    roleMutation.mutate({ userId: String(user.id), nextRoles });
                  };

                  return (
                    <div key={String(user.id)} className="flex flex-col gap-3 rounded-2xl border border-border/60 p-4 md:flex-row md:items-center md:justify-between">
                      <div>
                        <p className="font-semibold">{user.username || user.telegram_username || user.id}</p>
                        <p className="text-sm text-muted-foreground">
                          {user.telegram_username ? `@${user.telegram_username}` : `telegram:${user.telegram_id ?? "n/a"}`}
                        </p>
                        {isCurrentSessionUser && (
                          <p className="mt-1 text-xs text-muted-foreground">
                            {t("admin.selfRoleLocked")}
                          </p>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button
                          variant={currentRoles.includes("uploader") ? "default" : "outline"}
                          size="sm"
                          onClick={() => toggleRole("uploader")}
                          disabled={isCurrentSessionUser || roleMutation.isPending}
                        >
                          {t("admin.uploader")}
                        </Button>
                        <Button
                          variant={currentRoles.includes("admin") ? "default" : "outline"}
                          size="sm"
                          onClick={() => toggleRole("admin")}
                          disabled={isCurrentSessionUser || roleMutation.isPending}
                        >
                          {t("admin.adminRole")}
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </Card>
        )}
      </main>
    </div>
  );
}

function UploadedClipCard({
  clip,
  onTogglePublic,
  onDelete,
}: {
  clip: ClipDto;
  onTogglePublic: (nextPublic: boolean) => void;
  onDelete: () => void;
}) {
  const { t } = useI18n();
  const isReady = clip.status === "ready";
  const statusLabel = getStatusLabels(t);
  const statusIcon =
    clip.status === "ready" ? (
      <CheckCircle2 className="size-4" />
    ) : clip.status === "failed" ? (
      <AlertCircle className="size-4" />
    ) : (
      <LoaderCircle className="size-4 animate-spin" />
    );

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border border-border/60 bg-background p-4 shadow-sm"
    >
      <div className="flex flex-col gap-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate text-lg font-semibold">{clip.title}</p>
            <p className="mt-1 text-sm text-muted-foreground">{clip.description || t("admin.noInlineSubtitle")}</p>
          </div>
          <Badge variant={clip.status === "ready" ? "default" : clip.status === "failed" ? "destructive" : "secondary"}>
            <span className="inline-flex items-center gap-1">
              {statusIcon}
              {statusLabel[clip.status as QueueItemStatus] ?? clip.status}
            </span>
          </Badge>
        </div>

        <div className="flex flex-wrap gap-2 text-xs uppercase tracking-[0.2em] text-muted-foreground">
          <span>{clip.is_public ? t("admin.public") : t("admin.private")}</span>
          <span>{formatDuration(clip.duration_ms)}</span>
          <span>{formatBytes(clip.size_bytes ?? 0)}</span>
        </div>

        {isReady && clip.audio_url && (
          <audio controls src={clip.audio_url} className="w-full" preload="none" />
        )}

        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => onTogglePublic(!clip.is_public)}>
            {clip.is_public ? t("admin.makePrivate") : t("admin.makePublic")}
          </Button>
          <Button variant="outline" size="sm" onClick={onDelete}>
            <Trash2 />
            {t("admin.remove")}
          </Button>
        </div>
      </div>
    </motion.div>
  );
}

function ArrowUploadIcon() {
  return <Upload className="size-4" />;
}
