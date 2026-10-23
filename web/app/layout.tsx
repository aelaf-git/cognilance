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

/** Locked tab title for the marketing site. Do not change. */
const SITE_TITLE = "Cognilance AI";

export const metadata: Metadata = {
  metadataBase: new URL("https://cognilanceai.com"),
  title: {
    absolute: SITE_TITLE,
    default: SITE_TITLE,
  },
  description:
    "The AI Assistant for Teams. Shared agents, long-running work, and improvement with human approval. Join the waitlist.",
  icons: {
    icon: [{ url: "/brand/Cognilance-Logo.png", type: "image/png" }],
    apple: [{ url: "/brand/Cognilance-Logo.png", type: "image/png" }],
  },
  openGraph: {
    title: SITE_TITLE,
    description: "The AI Assistant for Teams. Join the waitlist.",
    images: ["/brand/Cognilance-Logo.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${spaceGrotesk.variable} ${ibmPlex.variable}`}
    >
      <body>{children}</body>
    </html>
  );
}
