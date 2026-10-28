import { Toaster } from "@/components/ui/sonner"
import { GlobalState } from "@/components/utility/global-state"
import { Providers } from "@/components/utility/providers"
import TranslationsProvider from "@/components/utility/translations-provider"
import initTranslations from "@/lib/i18n"
import { Metadata, Viewport } from "next"
import { IBM_Plex_Sans, Space_Grotesk } from "next/font/google"
import { ReactNode } from "react"
import "./globals.css"

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-space",
  display: "swap",
  weight: ["300", "400", "500", "600", "700"]
})

const ibmPlex = IBM_Plex_Sans({
  subsets: ["latin"],
  variable: "--font-plex",
  display: "swap",
  weight: ["400", "500", "600", "700"]
})

/** Locked tab title for the chatbot. Do not change. */
const APP_NAME = "Cognilance"
const APP_DEFAULT_TITLE = "Cognilance"
const APP_DESCRIPTION = "Cognilance chat"

interface RootLayoutProps {
  children: ReactNode
  params: {
    locale: string
  }
}

export const metadata: Metadata = {
  applicationName: APP_NAME,
  title: {
    absolute: APP_DEFAULT_TITLE,
    default: APP_DEFAULT_TITLE
  },
  description: APP_DESCRIPTION,
  icons: {
    icon: "/brand/Cognilance-Logo.png",
    apple: "/brand/Cognilance-Logo.png"
  },
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black",
    title: APP_DEFAULT_TITLE
    // startUpImage: [],
  },
  formatDetection: {
    telephone: false
  },
  openGraph: {
    type: "website",
    siteName: APP_NAME,
    title: APP_DEFAULT_TITLE,
    description: APP_DESCRIPTION
  },
  twitter: {
    card: "summary",
    title: APP_DEFAULT_TITLE,
    description: APP_DESCRIPTION
  }
}

export const viewport: Viewport = {
  themeColor: "#000000"
}

const i18nNamespaces = ["translation"]

export default async function RootLayout({
  children,
  params: { locale }
}: RootLayoutProps) {
  const { t, resources } = await initTranslations(locale, i18nNamespaces)

  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${spaceGrotesk.variable} ${ibmPlex.variable}`}
    >
      <body>
        <Providers attribute="class" defaultTheme="dark">
          <TranslationsProvider
            namespaces={i18nNamespaces}
            locale={locale}
            resources={resources}
          >
            <Toaster richColors position="top-center" duration={3000} />
            <div className="bg-background text-foreground flex h-dvh flex-col items-center overflow-x-auto">
              <GlobalState>{children}</GlobalState>
            </div>
          </TranslationsProvider>
        </Providers>
      </body>
    </html>
  )
}
