export const CSRF_COOKIE_NAME = "csrf_token";

const readCookieValue = (name: string): string | null => {
  if (typeof document === "undefined") {
    return null;
  }

  const tokenCookie = document.cookie
    .split(";")
    .map((cookie) => cookie.trim())
    .find((cookie) => cookie.startsWith(`${name}=`));

  if (!tokenCookie) {
    return null;
  }

  const [, rawValue] = tokenCookie.split("=");
  if (!rawValue) {
    return null;
  }

  try {
    return decodeURIComponent(rawValue);
  } catch {
    return null;
  }
};

export interface ResolveCsrfOptions {
  retries?: number;
  retryDelayMs?: number;
  validate?: (token: string) => boolean;
}

const defaultValidate = (token: string): boolean => {
  if (typeof token !== "string") {
    return false;
  }
  const trimmed = token.trim();
  return trimmed.length >= 8 && trimmed.length <= 512;
};

const sleep = (ms: number): Promise<void> =>
  new Promise((resolve) => {
    const timer =
      typeof window !== "undefined" && typeof window.setTimeout === "function"
        ? window.setTimeout
        : setTimeout;
    timer(resolve, ms);
  });

export const readCsrfToken = (): string | null => {
  return readCookieValue(CSRF_COOKIE_NAME);
};

export const resolveCsrfToken = async (
  options: ResolveCsrfOptions = {}
): Promise<string | null> => {
  const {
    retries = 2,
    retryDelayMs = 150,
    validate = defaultValidate,
  } = options;

  for (let attempt = 0; attempt <= retries; attempt += 1) {
    const token = readCsrfToken();
    if (token && validate(token)) {
      return token;
    }

    if (attempt < retries) {
      await sleep(retryDelayMs);
    }
  }

  return null;
};
