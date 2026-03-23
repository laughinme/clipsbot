import { cookies, headers } from "next/headers";

import { DEFAULT_LOCALE, LOCALE_COOKIE_NAME, SUPPORTED_LOCALES, type Locale, messages } from "./messages";

const normalizeLocale = (value: string | null | undefined): Locale | null => {
  if (!value) {
    return null;
  }

  const normalized = value.toLowerCase().split("-")[0];
  return SUPPORTED_LOCALES.includes(normalized as Locale) ? (normalized as Locale) : null;
};

export const resolveRequestLocale = async (): Promise<Locale> => {
  const cookieStore = await cookies();
  const cookieLocale = normalizeLocale(cookieStore.get(LOCALE_COOKIE_NAME)?.value);
  if (cookieLocale) {
    return cookieLocale;
  }

  const headerStore = await headers();
  const acceptLanguage = headerStore.get("accept-language");
  if (!acceptLanguage) {
    return DEFAULT_LOCALE;
  }

  for (const rawPart of acceptLanguage.split(",")) {
    const candidate = normalizeLocale(rawPart.split(";")[0]?.trim());
    if (candidate) {
      return candidate;
    }
  }

  return DEFAULT_LOCALE;
};

export const getMessagesForLocale = (locale: Locale) => messages[locale] ?? messages[DEFAULT_LOCALE];

