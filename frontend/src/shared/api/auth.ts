import apiProtected, { apiPublic } from "./axiosInstance";
import type {
  AuthTokens,
  AuthUser,
  BrowserAuthStartPayload,
  BrowserAuthStatusPayload
} from "@/entities/auth/model";

export const authenticateTelegram = async (initData: string): Promise<AuthTokens> => {
  const response = await apiPublic.post<AuthTokens>("/auth/telegram", {
    init_data: initData
  }, {
    withCredentials: true
  });
  return response.data;
};

export const logoutUser = async (): Promise<void> => {
  await apiProtected.post("/auth/logout");
};

export const getMyProfile = async (): Promise<AuthUser> => {
  const response = await apiProtected.get<AuthUser>("/users/me");
  return response.data;
};

export const startBrowserLogin = async (): Promise<BrowserAuthStartPayload> => {
  const response = await apiPublic.post<BrowserAuthStartPayload>("/auth/browser/start", {}, {
    withCredentials: true
  });
  return response.data;
};

export const getBrowserLoginStatus = async (challengeToken: string): Promise<BrowserAuthStatusPayload> => {
  const response = await apiPublic.get<BrowserAuthStatusPayload>(`/auth/browser/status/${challengeToken}`, {
    withCredentials: true
  });
  return response.data;
};

export const completeBrowserLogin = async (challengeToken: string): Promise<AuthTokens> => {
  const response = await apiPublic.post<AuthTokens>("/auth/browser/complete", {
    challenge_token: challengeToken
  }, {
    withCredentials: true
  });
  return response.data;
};
