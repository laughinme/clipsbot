import apiProtected, { apiPublic } from "./axiosInstance";

export type ClipDto = {
  id: string;
  title: string;
  slug: string;
  description?: string | null;
  object_key?: string | null;
  bucket?: string | null;
  mime_type?: string | null;
  duration_ms?: number | null;
  size_bytes?: number | null;
  status: "uploading" | "processing" | "ready" | "failed";
  is_public: boolean;
  uploaded_by_user_id?: string | null;
  audio_url?: string | null;
  download_url?: string | null;
  aliases: string[];
  created_at: string;
  updated_at?: string | null;
};

export type ClipListDto = {
  items: ClipDto[];
};

export type ClipUploadInitPayload = {
  title: string;
  description?: string;
  is_public: boolean;
  aliases: string[];
  filename: string;
  content_type: string;
};

export type ClipUploadInitResponseDto = {
  clip: ClipDto;
  upload_url: string;
  expires_in: number;
};

export const listPublicClips = async (search?: string): Promise<ClipDto[]> => {
  const response = await apiPublic.get<ClipListDto>("/public/clips/", {
    params: search ? { search } : undefined,
  });
  return response.data.items;
};

export const listAdminClips = async (): Promise<ClipDto[]> => {
  const response = await apiProtected.get<ClipListDto>("/admins/clips/");
  return response.data.items;
};

export const initClipUpload = async (payload: ClipUploadInitPayload): Promise<ClipUploadInitResponseDto> => {
  const response = await apiProtected.post<ClipUploadInitResponseDto>("/admins/clips/upload-init", payload);
  return response.data;
};

export const uploadClipObject = async (
  uploadUrl: string,
  file: File,
  onProgress?: (progress: number) => void,
): Promise<void> => {
  await new Promise<void>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("PUT", uploadUrl);
    request.setRequestHeader("Content-Type", file.type || "application/octet-stream");

    request.upload.onprogress = (event) => {
      if (!event.lengthComputable) {
        return;
      }
      onProgress?.(Math.min(100, Math.round((event.loaded / event.total) * 100)));
    };

    request.onerror = () => reject(new Error("Network error while uploading clip."));
    request.onload = () => {
      if (request.status >= 200 && request.status < 300) {
        onProgress?.(100);
        resolve();
        return;
      }
      reject(new Error(`Upload failed with status ${request.status}`));
    };

    request.send(file);
  });
};

export const finalizeClipUpload = async (clipId: string, objectKey: string): Promise<ClipDto> => {
  const response = await apiProtected.post<ClipDto>(`/admins/clips/${clipId}/finalize`, {
    object_key: objectKey,
  });
  return response.data;
};

export const updateClip = async (
  clipId: string,
  payload: Partial<Pick<ClipDto, "title" | "description" | "is_public">> & { aliases?: string[] }
): Promise<ClipDto> => {
  const response = await apiProtected.patch<ClipDto>(`/admins/clips/${clipId}`, payload);
  return response.data;
};

export const deleteClip = async (clipId: string): Promise<void> => {
  await apiProtected.delete(`/admins/clips/${clipId}`);
};
