export interface AuthTokens {
  access_token: string;
  refresh_token?: string;
  [key: string]: unknown;
}

export interface BrowserAuthStartPayload {
  challenge_token: string;
  status: string;
  expires_at: string;
  telegram_deep_link: string;
  telegram_bot_username: string;
}

export interface BrowserAuthStatusPayload {
  challenge_token: string;
  status: string;
  expires_at: string;
  approved_at?: string | null;
  approved_telegram_id?: number | null;
  approved_telegram_username?: string | null;
  approved_display_name?: string | null;
}

export interface AuthUser {
  id: string;
  telegram_id?: number | null;
  telegram_username?: string | null;
  username?: string | null;
  avatar_url?: string | null;
  role_slugs?: string[];
  roles?: string[];
  banned?: boolean;
  [key: string]: unknown;
}

export interface AuthContextValue {
  user: AuthUser | null;
  isUserLoading: boolean;
  isRestoringSession: boolean;
  authenticateTelegram: (initData: string) => Promise<AuthTokens>;
  completeBrowserLogin: (challengeToken: string) => Promise<AuthTokens>;
  logout: () => void;
  isAuthenticatingTelegram: boolean;
  isCompletingBrowserLogin: boolean;
  telegramAuthError: unknown;
  browserLoginError: unknown;
}
