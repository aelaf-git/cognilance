import type { Metadata } from "next";
import { IBM_Plex_Sans, Space_Grotesk } from "next/font/google";
import "./globals.css";

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-space",
  display: "swap",
  weight: ["300", "400", "500", "600", "700"],
});

const ibmPlex = IBM_Plex_Sans({
  subsets: ["latin"],
  variable: "--font-plex",
  display: "swap",
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  metadataBase: new URL("https://cognilance.ai"),
  title: "Cognilance AI",
  description:
    "Hire specialized AI agents you can see and control. Verified multi-agent orchestration built for production, not demos.",
  icons: {
    icon: [{ url: "/brand/icon.png", type: "image/png" }],
    apple: [{ url: "/brand/icon.png", type: "image/png" }],
  },
  openGraph: {
    title: "Cognilance AI",
    description:
      "Verified, persistent, unsupervised multi-agent orchestration.",
    images: ["/brand/logo.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${spaceGrotesk.variable} ${ibmPlex.variable}`}
        suppressHydrationWarning
      >
        {children}
      </body>
    </html>
  );
}
