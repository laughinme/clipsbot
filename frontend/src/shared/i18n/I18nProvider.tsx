"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";

import { DEFAULT_LOCALE, LOCALE_COOKIE_NAME, messages, SUPPORTED_LOCALES, type Locale, type Messages } from "./messages";

type I18nContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (path: string, values?: Record<string, string | number>) => string;
};

const I18nContext = createContext<I18nContextValue | null>(null);

const resolvePath = (source: unknown, path: string): string | null => {
  const value = path.split(".").reduce<unknown>((acc, segment) => {
    if (acc && typeof acc === "object" && segment in acc) {
      return (acc as Record<string, unknown>)[segment];
    }
    return null;
  }, source);

  return typeof value === "string" ? value : null;
};

const interpolate = (template: string, values?: Record<string, string | number>): string => {
  if (!values) {
    return template;
  }

  return template.replace(/\{(\w+)\}/g, (_, key: string) => String(values[key] ?? `{${key}}`));
};

export function I18nProvider({
  initialLocale,
  children,
}: {
  initialLocale: Locale;
  children: ReactNode;
}) {
  const router = useRouter();
  const [locale, setLocaleState] = useState<Locale>(initialLocale);

  useEffect(() => {
    setLocaleState(initialLocale);
  }, [initialLocale]);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = useCallback(
    (nextLocale: Locale) => {
      if (!SUPPORTED_LOCALES.includes(nextLocale) || nextLocale === locale) {
        return;
      }

      document.cookie = `${LOCALE_COOKIE_NAME}=${nextLocale}; Max-Age=31536000; Path=/; SameSite=Lax`;
      setLocaleState(nextLocale);
      router.refresh();
    },
    [locale, router],
  );

  const value = useMemo<I18nContextValue>(() => {
    const dictionary = (messages as Messages)[locale] ?? messages[DEFAULT_LOCALE];
    return {
      locale,
      setLocale,
      t: (path: string, values?: Record<string, string | number>) => {
        const resolved = resolvePath(dictionary, path) ?? resolvePath(messages[DEFAULT_LOCALE], path) ?? path;
        return interpolate(resolved, values);
      },
    };
  }, [locale, setLocale]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export const useI18n = (): I18nContextValue => {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error("useI18n must be used within I18nProvider");
  }
  return context;
};
