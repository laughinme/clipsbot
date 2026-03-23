"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { AuthProvider } from "@/app/providers/auth/AuthContext";
import { I18nProvider } from "@/shared/i18n/I18nProvider";
import type { Locale } from "@/shared/i18n/messages";
import { Toaster } from "@/shared/components/ui/sonner";

export function Providers({ children, initialLocale }: { children: ReactNode; initialLocale: Locale }) {
  const [queryClient] = useState(() => new QueryClient());

  return (
    <QueryClientProvider client={queryClient}>
      <I18nProvider initialLocale={initialLocale}>
        <AuthProvider>
          {children}
          <Toaster richColors position="top-center" />
        </AuthProvider>
      </I18nProvider>
    </QueryClientProvider>
  );
}
