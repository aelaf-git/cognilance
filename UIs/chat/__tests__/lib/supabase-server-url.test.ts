import { getSupabaseServerUrl } from "@/lib/supabase/server-url"

describe("getSupabaseServerUrl", () => {
  const originalInternal = process.env.SUPABASE_INTERNAL_URL
  const originalPublic = process.env.NEXT_PUBLIC_SUPABASE_URL

  afterEach(() => {
    if (originalInternal === undefined) {
      delete process.env.SUPABASE_INTERNAL_URL
    } else {
      process.env.SUPABASE_INTERNAL_URL = originalInternal
    }

    if (originalPublic === undefined) {
      delete process.env.NEXT_PUBLIC_SUPABASE_URL
    } else {
      process.env.NEXT_PUBLIC_SUPABASE_URL = originalPublic
    }
  })

  it("uses the internal URL when the server cannot reach the public host", () => {
    process.env.SUPABASE_INTERNAL_URL = "http://host.docker.internal:54321"
    process.env.NEXT_PUBLIC_SUPABASE_URL = "http://127.0.0.1:54321"

    expect(getSupabaseServerUrl()).toBe("http://host.docker.internal:54321")
  })

  it("falls back to the public URL outside Docker", () => {
    delete process.env.SUPABASE_INTERNAL_URL
    process.env.NEXT_PUBLIC_SUPABASE_URL = "http://127.0.0.1:54321"

    expect(getSupabaseServerUrl()).toBe("http://127.0.0.1:54321")
  })
})
