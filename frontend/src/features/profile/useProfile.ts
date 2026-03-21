import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { getProfile, patchProfile, uploadProfilePicture } from "@/shared/api/profile";
import type { UserPatchPayload } from "@/entities/user/model";

const PROFILE_KEY = ["profile", "me"] as const;

export function useProfile() {
    return useQuery({
        queryKey: PROFILE_KEY,
        queryFn: getProfile,
        staleTime: 1000 * 60 * 5,
    });
}

export function useUpdateProfile() {
    const qc = useQueryClient();

    return useMutation({
        mutationFn: (data: UserPatchPayload) => patchProfile(data),
        onSuccess: (updated) => {
            qc.setQueryData(PROFILE_KEY, updated);
            toast.success("Профиль обновлён");
        },
        onError: () => {
            toast.error("Не удалось обновить профиль");
        },
    });
}

export function useUploadAvatar() {
    const qc = useQueryClient();

    return useMutation({
        mutationFn: (file: File) => uploadProfilePicture(file),
        onSuccess: (updated) => {
            qc.setQueryData(PROFILE_KEY, updated);
            toast.success("Фото обновлено");
        },
        onError: () => {
            toast.error("Не удалось загрузить фото");
        },
    });
}
