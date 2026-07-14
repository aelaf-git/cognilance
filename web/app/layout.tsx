import type { Metadata } from "next";
import { Manrope, Syne } from "next/font/google";
import "./globals.css";

const syne = Syne({
  subsets: ["latin"],
  variable: "--font-syne",
  display: "swap",
  weight: ["600", "700", "800"],
});

const manrope = Manrope({
  subsets: ["latin"],
  variable: "--font-manrope",
  display: "swap",
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  metadataBase: new URL("https://cognilance.ai"),
  title: "Cognilance — Marketplace of Minds (Beta)",
  description:
    "One AI agent hallucinates. A thousand, verified, don't. Trustworthy autonomous AI built for production, not demos. Currently in beta.",
  openGraph: {
    title: "Cognilance — Marketplace of Minds",
    description:
      "Verified, persistent, unsupervised multi-agent orchestration. Currently in beta.",
    images: ["/logo.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${syne.variable} ${manrope.variable}`}>{children}</body>
    </html>
  );
}
