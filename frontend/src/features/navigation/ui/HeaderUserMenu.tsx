import { Link } from "react-router-dom";
import { IconLogout, IconUserCircle } from "@tabler/icons-react";

import { useAuth } from "@/app/providers/auth/useAuth";
import { useProfile } from "@/features/profile/useProfile";
import {
    Avatar,
    AvatarFallback,
    AvatarImage,
} from "@/shared/components/ui/avatar";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuGroup,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";
import { Skeleton } from "@/shared/components/ui/skeleton";

export function HeaderUserMenu() {
    const auth = useAuth();
    const { data: profile, isLoading } = useProfile();

    if (isLoading) {
        return <Skeleton className="h-8 w-8 rounded-full" />;
    }

    if (!profile) return null;

    const name = profile.username || profile.email;
    const initials = name
        .split(/[\s@]+/)
        .slice(0, 2)
        .map((s) => s[0]?.toUpperCase() ?? "")
        .join("");

    return (
        <DropdownMenu>
            <DropdownMenuTrigger asChild>
                <button
                    className="flex h-8 w-8 items-center justify-center overflow-hidden rounded-full ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 hover:bg-accent"
                >
                    <Avatar className="h-8 w-8 grayscale transition-all hover:grayscale-0">
                        {profile.profilePicUrl && (
                            <AvatarImage src={profile.profilePicUrl} alt={name} />
                        )}
                        <AvatarFallback>{initials}</AvatarFallback>
                    </Avatar>
                </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-56" align="end" sideOffset={8}>
                <DropdownMenuLabel className="font-normal">
                    <div className="flex flex-col space-y-1">
                        <p className="text-sm font-medium leading-none">{name}</p>
                        <p className="text-xs leading-none text-muted-foreground">
                            {profile.email}
                        </p>
                    </div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuGroup>
                    <DropdownMenuItem asChild>
                        <Link to="/profile" className="cursor-pointer">
                            <IconUserCircle className="mr-2 h-4 w-4" />
                            <span>Account</span>
                        </Link>
                    </DropdownMenuItem>
                </DropdownMenuGroup>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                    className="cursor-pointer text-destructive focus:bg-destructive focus:text-destructive-foreground"
                    onClick={() => auth?.logout()}
                >
                    <IconLogout className="mr-2 h-4 w-4" />
                    <span>Log out</span>
                </DropdownMenuItem>
            </DropdownMenuContent>
        </DropdownMenu>
    );
}
