import type { Metadata } from "next";
import Script from "next/script";

import { Providers } from "@/app/providers";
import { resolveRequestLocale } from "@/shared/i18n/server";
import "@/app/styles/index.css";

export const metadata: Metadata = {
  title: "ClipsBot",
  description: "Telegram inline audio catalog and admin studio.",
};

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const locale = await resolveRequestLocale();

  return (
    <html lang={locale}>
      <body>
        <Providers initialLocale={locale}>{children}</Providers>
        <Script src="https://telegram.org/js/telegram-web-app.js" strategy="beforeInteractive" />
      </body>
    </html>
  );
}
