import { createContext } from "react";
import type { AuthContextValue } from "@/entities/auth/model";

export const AuthContext = createContext<AuthContextValue | null>(null);
