import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

export type Schemas = components["schemas"];
export type LineId = Schemas["Line"];

export const api = createClient<paths>({
  // Absolute, so it also works where fetch doesn't resolve relative URLs (Node, in tests).
  baseUrl: new URL(import.meta.env.VITE_API_URL ?? "/api", window.location.origin).href,
  // Look fetch up on every call instead of capturing it once, so test mocks (MSW) apply.
  fetch: (request) => globalThis.fetch(request),
});

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, detail: unknown) {
    super(`API request failed with status ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

/** openapi-fetch returns `{ data, error }`; queries want a value or a thrown error. */
export async function unwrap<T>(
  request: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await request;
  if (data === undefined) throw new ApiError(response.status, error);
  return data;
}
