import tailwindcss from "@tailwindcss/vite";
import basicSsl from "@vitejs/plugin-basic-ssl";
import react from "@vitejs/plugin-react";
import type { PluginOption } from "vite";
import { defineConfig, loadEnv } from "vite";
import path from "path";

export default defineConfig(({ mode }) => {
  const env = {
    ...process.env,
    ...loadEnv(mode, process.cwd(), "")
  };
  const enableHttps = env.VITE_ENABLE_HTTPS !== "false";
  const proxyTarget = env.VITE_PROXY_TARGET ?? "http://localhost:8080";

  const plugins: PluginOption[] = [tailwindcss(), react()];
  if (enableHttps) {
    plugins.push(basicSsl());
  }

  return {
    plugins,
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src")
      }
    },
    server: {
      host: true,
      https: enableHttps ? {} : false,
      proxy: {
        "/api": {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
          followRedirects: true
        }
      }
    },
    preview: {
      https: enableHttps ? {} : false
    }
  };
});
