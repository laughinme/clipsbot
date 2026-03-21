import { useRef } from "react";
import { motion } from "motion/react";
import { IconCamera } from "@tabler/icons-react";

import {
    Avatar,
    AvatarImage,
    AvatarFallback,
} from "@/shared/components/ui/avatar";
import { useUploadAvatar } from "@/features/profile/useProfile";

interface ProfileAvatarUploadProps {
    src: string | null;
    username: string | null;
    email: string;
}

export function ProfileAvatarUpload({
    src,
    username,
    email,
}: ProfileAvatarUploadProps) {
    const inputRef = useRef<HTMLInputElement>(null);
    const { mutate: upload, isPending } = useUploadAvatar();

    const initials = (username ?? email)
        .split(/[\s@]+/)
        .slice(0, 2)
        .map((s) => s[0]?.toUpperCase() ?? "")
        .join("");

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            upload(file);
        }
        e.target.value = "";
    };

    return (
        <div className="relative group">
            <motion.button
                type="button"
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => inputRef.current?.click()}
                disabled={isPending}
                className="relative cursor-pointer rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-60 ring-4 ring-background z-10 bg-background"
            >
                <Avatar className="size-32 text-4xl sm:size-40 sm:text-5xl">
                    {src && <AvatarImage src={src} alt={username ?? email} />}
                    <AvatarFallback className="text-3xl sm:text-4xl font-medium">{initials}</AvatarFallback>
                </Avatar>

                <span className="absolute inset-0 flex items-center justify-center rounded-full bg-black/50 opacity-0 transition-opacity group-hover:opacity-100">
                    <IconCamera className="size-6 text-white" />
                </span>

                {isPending && (
                    <span className="absolute inset-0 flex items-center justify-center rounded-full bg-black/40">
                        <span className="size-6 animate-spin rounded-full border-2 border-white border-t-transparent" />
                    </span>
                )}
            </motion.button>

            <input
                ref={inputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
                onChange={handleFileChange}
            />
        </div>
    );
}
