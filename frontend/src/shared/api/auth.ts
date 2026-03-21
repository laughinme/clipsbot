import apiProtected, { apiPublic } from "./axiosInstance";
import type { AuthCredentials, AuthTokens, AuthUser } from "@/entities/auth/model";

export const registerUser = async (credentials: AuthCredentials): Promise<AuthTokens> => {
  const response = await apiPublic.post<AuthTokens>("/auth/register", credentials, {
    headers: { "X-Client": "web" },
    withCredentials: true
  });
  return response.data;
};

export const loginUser = async (credentials: AuthCredentials): Promise<AuthTokens> => {
  const response = await apiPublic.post<AuthTokens>("/auth/login", credentials, {
    headers: { "X-Client": "web" },
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
