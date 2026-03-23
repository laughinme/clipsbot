import apiProtected from "./axiosInstance";
import type { AuthUser } from "@/entities/auth/model";

type CursorPageDto<T> = {
  items: T[];
  next_cursor?: string | null;
};

export type RoleDto = {
  id: string;
  slug: string;
  name: string;
  description?: string | null;
};

export const listAdminUsers = async (): Promise<AuthUser[]> => {
  const response = await apiProtected.get<CursorPageDto<AuthUser>>("/admins/users/", {
    params: { limit: 50 },
  });
  return response.data.items;
};

export const listRoles = async (): Promise<RoleDto[]> => {
  const response = await apiProtected.get<RoleDto[]>("/admins/roles");
  return response.data;
};

export const setUserRoles = async (userId: string, roles: string[]): Promise<AuthUser> => {
  const response = await apiProtected.put<AuthUser>(`/admins/users/${userId}/roles`, { roles });
  return response.data;
};

export type UploaderInviteDto = {
  id: string;
  status: string;
  invite_link: string;
  expires_at: string;
  revoked_at?: string | null;
  consumed_at?: string | null;
  created_by_user_id?: string | null;
  consumed_by_user_id?: string | null;
  created_at: string;
  updated_at: string;
};

export const listUploaderInvites = async (): Promise<UploaderInviteDto[]> => {
  const response = await apiProtected.get<UploaderInviteDto[]>("/admins/uploader-invites/", {
    params: { limit: 20 },
  });
  return response.data;
};

export const createUploaderInvite = async (): Promise<UploaderInviteDto> => {
  const response = await apiProtected.post<UploaderInviteDto>("/admins/uploader-invites/");
  return response.data;
};

export const revokeUploaderInvite = async (inviteId: string): Promise<UploaderInviteDto> => {
  const response = await apiProtected.post<UploaderInviteDto>(`/admins/uploader-invites/${inviteId}/revoke`);
  return response.data;
};
