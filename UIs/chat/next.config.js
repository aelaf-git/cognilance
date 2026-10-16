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
    }
  })
)
