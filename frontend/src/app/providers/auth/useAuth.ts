import { useContext } from "react";
import { AuthContext } from "./AuthContextObject";
import type { AuthContextValue } from "@/entities/auth/model";

export const useAuth = (): AuthContextValue | null => useContext(AuthContext);
