"use client";

import Link from "next/link";
import { motion } from "motion/react";

import { useAuth } from "@/app/providers/auth/useAuth";
import { Button } from "@/shared/components/ui/button";
import { useI18n } from "@/shared/i18n/I18nProvider";

export function Header() {
    const auth = useAuth();
    const { locale, setLocale, t } = useI18n();
    const roles = auth?.user?.role_slugs ?? auth?.user?.roles ?? [];
    const canAdmin = roles.includes("admin") || roles.includes("uploader");

    return (
        <motion.header
            initial={{ y: -100, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/60"
        >
            <div className="container mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-8">
                <div className="flex items-center gap-6">
                    <Link href="/" className="flex items-center space-x-2">
                        <motion.div
                            whileHover={{ scale: 1.05 }}
                            whileTap={{ scale: 0.95 }}
                            className="bg-foreground text-background font-bold px-2 py-1 rounded-md text-sm tracking-widest uppercase transition-colors"
                        >
                            ClipsBot
                        </motion.div>
                    </Link>

                    <nav className="hidden md:flex gap-6">
                        <motion.div whileHover={{ y: -1 }}>
                            <Link
                                href="/catalog"
                                className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
                            >
                                {t("header.catalog")}
                            </Link>
                        </motion.div>
                        {canAdmin && (
                            <motion.div whileHover={{ y: -1 }}>
                                <Link
                                    href="/admin"
                                    className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
                                >
                                    {t("header.admin")}
                                </Link>
                            </motion.div>
                        )}
                    </nav>
                </div>

                <div className="flex items-center gap-4">
                    <motion.div className="md:hidden" whileHover={{ y: -1 }}>
                        <Link
                            href="/catalog"
                            className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
                        >
                            {t("header.catalog")}
                        </Link>
                    </motion.div>
                    <div className="flex items-center gap-1 rounded-full border border-border/60 p-1">
                        <Button
                            type="button"
                            variant={locale === "ru" ? "default" : "ghost"}
                            size="sm"
                            className="h-8 px-2"
                            onClick={() => setLocale("ru")}
                        >
                            {t("language.ru")}
                        </Button>
                        <Button
                            type="button"
                            variant={locale === "en" ? "default" : "ghost"}
                            size="sm"
                            className="h-8 px-2"
                            onClick={() => setLocale("en")}
                        >
                            {t("language.en")}
                        </Button>
                    </div>
                    {auth?.user && (
                        <>
                            <span className="hidden text-sm text-muted-foreground sm:block">
                                {auth.user.username || auth.user.telegram_username || `telegram:${auth.user.telegram_id ?? t("header.userFallback")}`}
                            </span>
                            <Button variant="outline" size="sm" onClick={() => auth.logout()}>
                                {t("header.logout")}
                            </Button>
                        </>
                    )}
                </div>
            </div>
        </motion.header>
    );
}
