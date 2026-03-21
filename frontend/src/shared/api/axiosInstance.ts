import axios, {
  type AxiosError,
  AxiosHeaders,
  type AxiosInstance,
  type AxiosRequestHeaders,
  type AxiosResponse,
  type InternalAxiosRequestConfig
} from "axios";
import type { AuthTokens } from "@/entities/auth/model";
import { withBasePath } from "@/shared/lib/utils";
import { resolveCsrfToken } from "../lib/csrf";
const DEFAULT_API_PATH = "/api/v1";
const BASE_URL = withBasePath(
  import.meta.env.VITE_API_BASE_URL as string | undefined,
  DEFAULT_API_PATH
);

export const apiPublic: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: {
    "Content-Type": "application/json"
  },
  withCredentials: true
});

let accessToken: string | null = null;
let unauthorizedHandler: (() => void) | null = null;
let refreshPromise: Promise<string | null> | null = null;

export const setAccessToken = (token: string | null): void => {
  accessToken = token;
};

export const getAccessToken = (): string | null => accessToken;

export const setUnauthorizedHandler = (handler: (() => void) | null): void => {
  unauthorizedHandler = typeof handler === "function" ? handler : null;
};

const notifyUnauthorized = (): void => {
  setAccessToken(null);
  if (unauthorizedHandler) {
    unauthorizedHandler();
  }
};

const toAxiosHeaders = (headers?: AxiosRequestHeaders): AxiosHeaders => {
  if (headers instanceof AxiosHeaders) {
    return headers;
  }
  return new AxiosHeaders(headers ?? {});
};

const apiProtected: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: {
    "Content-Type": "application/json"
  },
  withCredentials: true
});

const normalizePath = (value?: string): string | undefined => {
  if (!value) {
    return value;
  }
  return value.replace(/\/+$/, "");
};

export const refreshAccessToken = async (): Promise<string | null> => {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const csrfToken = await resolveCsrfToken();
      if (!csrfToken) {
        return null;
      }

      const { data } = await apiPublic.post<AuthTokens>(
        "/auth/refresh",
        {},
        {
          headers: { "X-CSRF-Token": csrfToken },
          withCredentials: true
        }
      );

      return data?.access_token ?? null;
    })().finally(() => {
      refreshPromise = null;
    });
  }

  return refreshPromise;
};

apiProtected.interceptors.request.use(
  (config: InternalAxiosRequestConfig): InternalAxiosRequestConfig => {
    const token = getAccessToken();
    if (token) {
      const headers = toAxiosHeaders(config.headers);
      headers.set("Authorization", `Bearer ${token}`);
      config.headers = headers;
    }
    return config;
  },
  (error: AxiosError): Promise<never> => Promise.reject(error)
);

apiProtected.interceptors.response.use(
  (response: AxiosResponse): AxiosResponse => response,
  async (error: AxiosError): Promise<AxiosResponse | never> => {
    const originalRequest = (error.config as (InternalAxiosRequestConfig & { _retry?: boolean })) ?? null;

    const originalUrl = normalizePath(originalRequest?.url);
    if (
      error?.response?.status === 401 &&
      originalRequest &&
      originalUrl !== "/auth/refresh" &&
      !originalRequest._retry
    ) {
      originalRequest._retry = true;
      try {
        const newAccessToken = await refreshAccessToken();
        if (newAccessToken) {
          setAccessToken(newAccessToken);
          const headers = toAxiosHeaders(originalRequest.headers);
          headers.set("Authorization", `Bearer ${newAccessToken}`);
          originalRequest.headers = headers;
          return apiProtected(originalRequest);
        }

        notifyUnauthorized();
      } catch {
        notifyUnauthorized();
      }
    }
    return Promise.reject(error);
  }
);

export default apiProtected;
