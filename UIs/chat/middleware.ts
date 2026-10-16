import i18nConfig from "./i18nConfig"
import { i18nRouter } from "next-i18n-router"
import { NextResponse, type NextRequest } from "next/server"

function isHomePath(pathname: string) {
  if (pathname === "/" || pathname === "") return true
  return i18nConfig.locales.some(
    locale => pathname === `/${locale}` || pathname === `/${locale}/`
  )
}

export async function middleware(request: NextRequest) {
  if (isHomePath(request.nextUrl.pathname)) {
    return NextResponse.redirect(new URL("/local/chat", request.url))
  }

  return i18nRouter(request, i18nConfig)
}

export const config = {
  matcher: "/((?!api|static|.*\\..*|_next|auth).*)"
}
