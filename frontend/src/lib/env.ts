/** True when deployed production build (Railway/Render). */
export const isProductionApp =
  process.env.NEXT_PUBLIC_APP_ENV === "production";

/** Public app URL — align with backend FRONTEND_URL in production. */
export const FRONTEND_BASE =
  process.env.NEXT_PUBLIC_FRONTEND_URL ?? "http://localhost:3000";
