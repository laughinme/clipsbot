import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";


export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}


export function withBasePath(base: string | undefined, path: string): string {
  if (!base) {
    return path;
  }

  const normalizedBase = base.replace(/\/+$/, "");
  const normalizedPath = path.replace(/^\/+/, "");

  return `${normalizedBase}/${normalizedPath}`;
}
