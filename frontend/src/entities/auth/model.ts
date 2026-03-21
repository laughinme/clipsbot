export interface AuthCredentials {
  email: string;
  password: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token?: string;
  [key: string]: unknown;
}

export interface AuthUser {
  email: string;
  [key: string]: unknown;
}

export interface AuthContextValue {
  user: AuthUser | null;
  isUserLoading: boolean;
  isRestoringSession: boolean;
  login: (credentials: AuthCredentials) => Promise<AuthTokens>;
  register: (credentials: AuthCredentials) => Promise<AuthTokens>;
  logout: () => void;
  isLoggingIn: boolean;
  loginError: unknown;
  isRegistering: boolean;
  registerError: unknown;
}
