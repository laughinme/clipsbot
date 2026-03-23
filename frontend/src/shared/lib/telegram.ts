declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initData?: string;
        ready: () => void;
        expand: () => void;
      };
    };
  }
}

const getUrlParams = (raw: string): URLSearchParams => {
  const normalized = raw.startsWith("#") || raw.startsWith("?") ? raw.slice(1) : raw;
  return new URLSearchParams(normalized);
};

const getInitDataFromLocation = (): string | null => {
  if (typeof window === "undefined") {
    return null;
  }

  const fromHash = getUrlParams(window.location.hash).get("tgWebAppData");
  if (fromHash) {
    return fromHash;
  }

  const fromSearch = getUrlParams(window.location.search).get("tgWebAppData");
  if (fromSearch) {
    return fromSearch;
  }

  return null;
};

export const getTelegramInitData = (): string | null => {
  if (typeof window === "undefined") {
    return null;
  }

  const initData = window.Telegram?.WebApp?.initData?.trim();
  if (initData) {
    return initData;
  }

  return getInitDataFromLocation();
};

export const isTelegramMiniApp = (): boolean => {
  if (typeof window === "undefined") {
    return false;
  }

  return Boolean(getTelegramInitData());
};

export const prepareTelegramWebApp = (): void => {
  if (typeof window === "undefined") {
    return;
  }
  if (!getTelegramInitData()) {
    return;
  }
  window.Telegram?.WebApp?.ready();
  window.Telegram?.WebApp?.expand();
};
