const fs = require("fs")
const path = require("path")

function readEnvFile(filename) {
  const full = path.join(__dirname, filename)
  if (!fs.existsSync(full)) return {}
  const out = {}
  for (const line of fs.readFileSync(full, "utf8").split(/\r?\n/)) {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith("#")) continue
    const eq = trimmed.indexOf("=")
    if (eq < 0) continue
    const key = trimmed.slice(0, eq).trim()
    let value = trimmed.slice(eq + 1).trim()
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1)
    }
    if (value) out[key] = value
  }
  return out
}

// Next does not override env vars that are already set. An empty
// NEXT_PUBLIC_* from the container blocks .env.local and gets inlined as "".
const fileEnv = readEnvFile(".env.local")
const supabaseUrl =
  process.env.NEXT_PUBLIC_SUPABASE_URL || fileEnv.NEXT_PUBLIC_SUPABASE_URL
const supabaseKey =
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
  fileEnv.NEXT_PUBLIC_SUPABASE_ANON_KEY

const withBundleAnalyzer = require("@next/bundle-analyzer")({
  enabled: process.env.ANALYZE === "true"
})

const withPWA = require("next-pwa")({
  dest: "public",
  // GenerateSW in next dev / webpack watch corrupts the chunk graph and
  // surfaces as ChunkLoadError timeouts on app/[locale]/layout.js.
  disable: process.env.NODE_ENV === "development"
})

module.exports = withBundleAnalyzer(
  withPWA({
    reactStrictMode: true,
    skipTrailingSlashRedirect: true,
    images: {
      remotePatterns: [
        {
          protocol: "http",
          hostname: "localhost"
        },
        {
          protocol: "http",
          hostname: "127.0.0.1"
        },
        {
          protocol: "https",
          hostname: "**"
        }
      ]
    },
    experimental: {
      serverComponentsExternalPackages: ["sharp", "onnxruntime-node"]
    },
    env: {
      ...(supabaseUrl ? { NEXT_PUBLIC_SUPABASE_URL: supabaseUrl } : {}),
      ...(supabaseKey ? { NEXT_PUBLIC_SUPABASE_ANON_KEY: supabaseKey } : {})
    }
  })
)
