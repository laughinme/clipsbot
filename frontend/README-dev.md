# Frontend Dev Presets

This file explains how frontend API routing works in this project and gives ready-to-use presets.

## How It Works

- `axiosInstance.ts` builds API base from `VITE_API_BASE_URL` + `/api/v1`.
- If `VITE_API_BASE_URL` is empty, frontend uses relative URLs (`/api/v1/...`).
- In `vite dev`, relative `/api/*` is proxied to `VITE_PROXY_TARGET` (see `vite.config.ts`).
- If `VITE_API_BASE_URL` is absolute (for example `https://api.example.com`), browser calls it directly and Vite proxy is bypassed.

## Recommended Local Flow (Frontend + Docker Backend)

1. Start backend stack from project root:

```bash
docker compose up -d backend db redis minio minio-init
```

2. Apply local preset:

```bash
cp env-presets/local-backend.env .env.local
```

3. Run frontend:

```bash
npm run dev
```

## Switch To Live Backend Quickly

Recommended option (through Vite proxy, simpler for auth/cookies in dev):

```bash
cp env-presets/live-backend-proxy.env .env.local
```

Then set your real backend URL in `.env.local`:

```env
VITE_PROXY_TARGET=https://your-api-domain
```

Run:

```bash
npm run dev
```

## Optional Direct Mode (Without Vite Proxy)

Use only if you intentionally want direct browser calls to live backend:

```bash
cp env-presets/live-backend-direct.env .env.local
npm run dev
```

In this mode `VITE_PROXY_TARGET` is ignored for API calls.

## Variables Summary

- `VITE_API_BASE_URL`: API origin for direct calls. Keep empty for proxy mode.
- `VITE_PROXY_TARGET`: backend target for Vite `/api` proxy.
- `VITE_ENABLE_HTTPS`: enables/disables local HTTPS for Vite dev server.

## Notes

- Restart `npm run dev` after changing `.env.local`.
- `.env.local` is ignored by git, so each teammate can keep their own setup.
