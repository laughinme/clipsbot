import apiProtected from "./axiosInstance";
import { toUser, toUserPatchDto } from "@/entities/user/model";
import type { User, UserPatchPayload } from "@/entities/user/model";

export type UserDto = {
    id: string;
    email: string;
    username: string | null;
    avatar_key?: string | null;
    avatar_url?: string | null;
    profile_pic_url?: string | null;
    bio?: string | null;
    is_onboarded: boolean;
    banned: boolean;
    role_slugs?: string[];
    roles?: string[];
    created_at: string;
    updated_at: string | null;
};

export type UserPatchPayloadDto = {
    username?: string | null;
    bio?: string | null;
};

type AvatarPresignRequestDto = {
    filename: string;
    content_type: string;
};

type AvatarPresignResponseDto = {
    object_key: string;
    upload_url: string;
    public_url: string;
    expires_in: number;
};

type AvatarConfirmRequestDto = {
    object_key: string;
};

const requestAvatarPresign = async (file: File): Promise<AvatarPresignResponseDto> => {
    const payload: AvatarPresignRequestDto = {
        filename: file.name,
        content_type: file.type,
    };

    const response = await apiProtected.post<AvatarPresignResponseDto>(
        "/users/me/avatar/presign",
        payload
    );
    return response.data;
};

const uploadToPresignedUrl = async (uploadUrl: string, file: File): Promise<void> => {
    const uploadResult = await fetch(uploadUrl, {
        method: "PUT",
        headers: {
            "Content-Type": file.type,
        },
        body: file,
    });

    if (!uploadResult.ok) {
        throw new Error(`Avatar upload failed with status ${uploadResult.status}`);
    }
};

const confirmAvatarUpload = async (objectKey: string): Promise<User> => {
    const payload: AvatarConfirmRequestDto = { object_key: objectKey };
    const response = await apiProtected.post<UserDto>("/users/me/avatar/confirm", payload);
    return toUser(response.data);
};

export const getProfile = async (): Promise<User> => {
    const response = await apiProtected.get<UserDto>("/users/me");
    return toUser(response.data);
};

export const patchProfile = async (
    data: UserPatchPayload
): Promise<User> => {
    const dto = toUserPatchDto(data);
    const response = await apiProtected.patch<UserDto>("/users/me", dto);
    return toUser(response.data);
};

export const uploadProfilePicture = async (
    file: File
): Promise<User> => {
    const { upload_url: uploadUrl, object_key: objectKey } = await requestAvatarPresign(file);
    await uploadToPresignedUrl(uploadUrl, file);
    return confirmAvatarUpload(objectKey);
};
