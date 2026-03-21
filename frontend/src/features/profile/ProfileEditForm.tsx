import { useState, useEffect } from "react";
import { motion } from "motion/react";

import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
    CardDescription,
    CardFooter,
} from "@/shared/components/ui/card";
import { useUpdateProfile } from "@/features/profile/useProfile";
import type { User, UserPatchPayload } from "@/entities/user/model";

interface ProfileEditFormProps {
    profile: User;
}

export function ProfileEditForm({ profile }: ProfileEditFormProps) {
    const [form, setForm] = useState<UserPatchPayload>({
        username: profile.username ?? "",
        bio: profile.bio ?? "",
    });

    useEffect(() => {
        setForm({
            username: profile.username ?? "",
            bio: profile.bio ?? "",
        });
    }, [profile.username, profile.bio]);

    const { mutate: save, isPending } = useUpdateProfile();

    const hasChanges =
        (form.username ?? "") !== (profile.username ?? "") ||
        (form.bio ?? "") !== (profile.bio ?? "");

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();

        const payload: UserPatchPayload = {};
        if ((form.username ?? "") !== (profile.username ?? "")) {
            payload.username = form.username || null;
        }
        if ((form.bio ?? "") !== (profile.bio ?? "")) {
            payload.bio = form.bio || null;
        }

        save(payload);
    };

    const handleReset = () => {
        setForm({
            username: profile.username ?? "",
            bio: profile.bio ?? "",
        });
    };

    return (
        <Card className="border-none shadow-none bg-transparent">
            <CardHeader className="px-0 pt-0">
                <CardTitle className="text-2xl">Личная информация</CardTitle>
                <CardDescription className="text-base">
                    Обновите своё имя и описание
                </CardDescription>
            </CardHeader>

            <form onSubmit={handleSubmit}>
                <CardContent className="space-y-6 px-0 pb-6">
                    <div className="space-y-3">
                        <Label htmlFor="profile-username" className="text-sm font-semibold text-foreground/80">Имя пользователя</Label>
                        <Input
                            id="profile-username"
                            placeholder="Введите имя"
                            className="h-11 px-4 text-base bg-muted/40 border-border/50 focus-visible:bg-transparent"
                            value={form.username ?? ""}
                            onChange={(e) =>
                                setForm((p) => ({ ...p, username: e.target.value }))
                            }
                        />
                    </div>

                    <div className="space-y-3">
                        <Label htmlFor="profile-bio" className="text-sm font-semibold text-foreground/80">О себе</Label>
                        <textarea
                            id="profile-bio"
                            placeholder="Расскажите о себе..."
                            rows={4}
                            className="w-full min-w-0 rounded-md border border-border/50 bg-muted/40 px-4 py-3 text-base shadow-xs transition-[color,box-shadow] outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:bg-transparent focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-input/20 resize-none"
                            value={form.bio ?? ""}
                            onChange={(e) =>
                                setForm((p) => ({ ...p, bio: e.target.value }))
                            }
                        />
                    </div>
                </CardContent>

                <CardFooter className="flex gap-3 justify-end px-0 pt-2 border-none">
                    <Button
                        type="button"
                        variant="ghost"
                        size="lg"
                        disabled={!hasChanges || isPending}
                        onClick={handleReset}
                    >
                        Отмена
                    </Button>

                    <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
                        <Button
                            type="submit"
                            size="lg"
                            className="font-semibold"
                            disabled={!hasChanges || isPending}
                        >
                            {isPending ? "Сохранение..." : "Сохранить"}
                        </Button>
                    </motion.div>
                </CardFooter>
            </form>
        </Card>
    );
}
