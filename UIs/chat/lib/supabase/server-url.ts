/**
 * URL the Next.js server uses to reach Supabase.
 * The browser keeps NEXT_PUBLIC_SUPABASE_URL (reachable from the host).
 * Docker sets SUPABASE_INTERNAL_URL because 127.0.0.1 inside the container
 * is the container, not the Supabase API on the host.
 */
export function getSupabaseServerUrl(): string {
  return (
    process.env.SUPABASE_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_SUPABASE_URL ||
    ""
  )
}
