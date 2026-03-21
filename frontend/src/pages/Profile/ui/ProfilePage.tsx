import * as React from "react";
import { motion } from "motion/react";
import { IconCalendar, IconMail, IconShieldCheck } from "@tabler/icons-react";

import { Header } from "@/features/navigation/ui/Header";
import { Badge } from "@/shared/components/ui/badge";
import { Separator } from "@/shared/components/ui/separator";
import { Skeleton } from "@/shared/components/ui/skeleton";

import { useProfile } from "@/features/profile/useProfile";
import { ProfileAvatarUpload } from "@/features/profile/ProfileAvatarUpload";
import { ProfileEditForm } from "@/features/profile/ProfileEditForm";

const container = {
    hidden: { opacity: 0 },
    show: {
        opacity: 1,
        transition: { staggerChildren: 0.1, delayChildren: 0.05 },
    },
};

const item = {
    hidden: { opacity: 0, y: 16 },
    show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.25, 0.1, 0.25, 1] } },
} as const;

function formatDate(iso: string | null | undefined): string {
    if (!iso) return "—";
    return new Date(iso).toLocaleDateString("ru-RU", {
        day: "numeric",
        month: "long",
        year: "numeric",
    });
}

function ProfileSkeleton() {
    return (
        <div className="mx-auto w-full max-w-2xl space-y-6 py-10 px-4">
            <div className="flex items-center gap-6">
                <Skeleton className="size-24 rounded-full" />
                <div className="space-y-2">
                    <Skeleton className="h-5 w-40" />
                    <Skeleton className="h-4 w-56" />
                </div>
            </div>
            <Skeleton className="h-64 w-full rounded-xl" />
            <Skeleton className="h-40 w-full rounded-xl" />
        </div>
    );
}

export default function ProfilePage() {
    const { data: profile, isLoading, isError } = useProfile();

    return (
        <div className="min-h-screen bg-background flex flex-col font-sans relative">
            <Header />

            <div className="absolute top-16 left-0 right-0 h-48 sm:h-64 bg-gradient-to-r from-neutral-200 to-neutral-300 dark:from-neutral-800 dark:to-neutral-900 border-b border-border/40 z-0"></div>

            <main className="flex-1 w-full max-w-5xl mx-auto px-4 lg:px-6 pt-40 sm:pt-56 pb-12 relative z-10">
                {isLoading && <ProfileSkeleton />}

                {isError && (
                    <div className="mx-auto max-w-2xl py-20 text-center text-muted-foreground mt-12 bg-card rounded-xl border p-8">
                        Не удалось загрузить профиль. Попробуйте обновить страницу.
                    </div>
                )}

                {profile && (
                    <motion.div
                        className="flex flex-col md:flex-row gap-8 lg:gap-12"
                        variants={container}
                        initial="hidden"
                        animate="show"
                    >
                        <motion.div variants={item} className="w-full md:w-1/3 flex flex-col items-center md:items-start text-center md:text-left gap-6">
                            <div className="-mt-12 sm:-mt-20">
                                <ProfileAvatarUpload
                                    src={profile.profilePicUrl}
                                    username={profile.username}
                                    email={profile.email}
                                />
                            </div>

                            <div className="space-y-1 w-full">
                                <h1 className="truncate text-3xl font-extrabold tracking-tight">
                                    {profile.username || profile.email}
                                </h1>
                                <p className="truncate text-base text-muted-foreground font-medium">
                                    {profile.email}
                                </p>
                            </div>

                            {profile.roles && profile.roles.length > 0 && (
                                <div className="flex flex-wrap gap-2 justify-center md:justify-start">
                                    {profile.roles.map((role) => (
                                        <Badge key={role} variant="secondary" className="text-xs px-2.5 py-0.5">
                                            {role}
                                        </Badge>
                                    ))}
                                </div>
                            )}

                            <Separator className="w-full" />

                            <div className="w-full space-y-4 text-sm">
                                <div className="flex items-center text-muted-foreground">
                                    <IconMail className="size-4 mr-3" />
                                    <span>{profile.email}</span>
                                </div>

                                <div className="flex items-center text-muted-foreground">
                                    <IconCalendar className="size-4 mr-3" />
                                    <span>В сети с {formatDate(profile.createdAt)}</span>
                                </div>

                                <div className="flex items-center text-muted-foreground">
                                    <IconShieldCheck className="size-4 mr-3" />
                                    {profile.banned ? (
                                        <Badge variant="destructive" className="h-5 rounded-sm px-1.5 text-[10px] font-semibold uppercase">Забанен</Badge>
                                    ) : (
                                        <Badge variant="outline" className="h-5 rounded-sm px-1.5 text-[10px] font-semibold uppercase border-foreground/20 text-foreground/70">Активен</Badge>
                                    )}
                                </div>
                            </div>
                        </motion.div>

                        <motion.div variants={item} className="w-full md:w-2/3 flex flex-col pt-4 md:pt-8">
                            <ProfileEditForm profile={profile} />
                        </motion.div>
                    </motion.div>
                )}
            </main>
        </div>
    );
}
