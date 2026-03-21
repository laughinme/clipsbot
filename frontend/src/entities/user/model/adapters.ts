import type { UserDto, UserPatchPayloadDto } from "@/shared/api/profile";
import type { User, UserPatchPayload } from "./types";

export const toUser = (dto: UserDto): User => ({
    id: dto.id,
    email: dto.email,
    username: dto.username,
    profilePicUrl: dto.avatar_url ?? dto.profile_pic_url ?? null,
    bio: dto.bio ?? null,
    isOnboarded: dto.is_onboarded,
    banned: dto.banned,
    roles: dto.role_slugs ?? dto.roles ?? [],
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
});

export const toUserPatchDto = (patch: UserPatchPayload): UserPatchPayloadDto => {
    const dto: UserPatchPayloadDto = {};
    if (patch.username !== undefined) dto.username = patch.username;
    if (patch.bio !== undefined) dto.bio = patch.bio;
    return dto;
};
