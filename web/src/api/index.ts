import { createHttpClient, type AuLacApi } from "./client";

let client: AuLacApi | null = null;

export function getApi(): AuLacApi {
  if (!client) client = createHttpClient(process.env.NEXT_PUBLIC_API_BASE_URL ?? "");
  return client;
}

export type { AuLacApi } from "./client";
export * from "./types";
export { qk, MATRIX_AFFECTED } from "./query-keys";
