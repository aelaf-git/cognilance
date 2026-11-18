export const dynamic = "force-dynamic"
export const runtime = "nodejs"

const COORDINATOR_URL =
  process.env.COGNILANCE_COORDINATOR_URL || "http://127.0.0.1:8200"

function allowed(method: string, path: string) {
  return (
    (method === "POST" && path === "auth/register") ||
    (method === "POST" && path === "auth/login") ||
    (method === "POST" && path === "auth/logout") ||
    (method === "POST" && path === "auth/password") ||
    (method === "GET" && path === "auth/me") ||
    (method === "PATCH" && path === "auth/me") ||
    (method === "GET" && path === "conversations") ||
    (method === "POST" && path === "conversations") ||
    (method === "GET" && path === "integrations/list") ||
    (method === "GET" && path === "organizations") ||
    (method === "GET" && path === "invitations") ||
    /^POST organizations\/[^/]+\/invitations$/.test(`${method} ${path}`) ||
    /^GET organizations\/[^/]+\/conversations$/.test(`${method} ${path}`) ||
    /^GET organizations\/[^/]+\/runs$/.test(`${method} ${path}`) ||
    /^GET organizations\/[^/]+\/integrations$/.test(`${method} ${path}`) ||
    /^DELETE organizations\/[^/]+$/.test(`${method} ${path}`) ||
    /^POST invitations\/[^/]+\/accept$/.test(`${method} ${path}`) ||
    ((method === "GET" || method === "POST") && path === "projects") ||
    /^GET projects\/[^/]+$/.test(`${method} ${path}`) ||
    /^PATCH projects\/[^/]+$/.test(`${method} ${path}`) ||
    /^DELETE projects\/[^/]+$/.test(`${method} ${path}`) ||
    /^GET projects\/[^/]+\/tasks$/.test(`${method} ${path}`) ||
    /^POST projects\/[^/]+\/tasks$/.test(`${method} ${path}`) ||
    /^GET projects\/[^/]+\/tasks\/[^/]+$/.test(`${method} ${path}`) ||
    /^PATCH projects\/[^/]+\/tasks\/[^/]+$/.test(`${method} ${path}`) ||
    /^DELETE projects\/[^/]+\/tasks\/[^/]+$/.test(`${method} ${path}`) ||
    /^POST projects\/[^/]+\/tasks\/[^/]+\/comments$/.test(`${method} ${path}`) ||
    /^GET projects\/[^/]+\/tasks\/[^/]+\/activity$/.test(`${method} ${path}`) ||
    /^GET conversations\/[^/]+$/.test(`${method} ${path}`) ||
    /^DELETE conversations\/[^/]+$/.test(`${method} ${path}`) ||
    /^GET conversations\/[^/]+\/sessions$/.test(`${method} ${path}`) ||
    /^GET integrations\/logos\/[^/]+$/.test(`${method} ${path}`) ||
    /^GET integrations\/[^/]+\/connect$/.test(`${method} ${path}`) ||
    /^POST integrations\/[^/]+\/disconnect$/.test(`${method} ${path}`) ||
    /^POST sessions\/[^/]+\/abort$/.test(`${method} ${path}`) ||
    /^POST sessions\/[^/]+\/start$/.test(`${method} ${path}`)
  )
}

function copyCookies(upstream: Response, headers: Headers) {
  const cookies =
    typeof upstream.headers.getSetCookie === "function"
      ? upstream.headers.getSetCookie()
      : []
  for (const cookie of cookies) headers.append("set-cookie", cookie)
}

async function proxy(request: Request, path: string[]) {
  if (path.some(part => !part || part === "." || part === "..")) {
    return Response.json({ error: "Not found" }, { status: 404 })
  }
  const joined = path.join("/")
  if (!allowed(request.method, joined)) {
    return Response.json({ error: "Not found" }, { status: 404 })
  }

  const headers = new Headers()
  const cookie = request.headers.get("cookie")
  if (cookie) headers.set("cookie", cookie)
  if (request.method !== "GET" && request.method !== "HEAD") {
    headers.set("Content-Type", "application/json")
  }

  let upstream: Response
  try {
    upstream = await fetch(`${COORDINATOR_URL}/${joined}`, {
      method: request.method,
      headers,
      body:
        request.method === "GET" || request.method === "HEAD"
          ? undefined
          : await request.text(),
      redirect: "manual"
    })
  } catch {
    return Response.json(
      { error: "Cognilance coordinator is not running." },
      { status: 502 }
    )
  }

  const location = upstream.headers.get("location")
  if (
    location &&
    (upstream.status === 301 ||
      upstream.status === 302 ||
      upstream.status === 303 ||
      upstream.status === 307 ||
      upstream.status === 308)
  ) {
    const redirectHeaders = new Headers({ location })
    copyCookies(upstream, redirectHeaders)
    return new Response(null, {
      status: upstream.status,
      headers: redirectHeaders
    })
  }

  const responseHeaders = new Headers({
    "Content-Type":
      upstream.headers.get("content-type") || "application/json"
  })
  copyCookies(upstream, responseHeaders)
  return new Response(upstream.body, {
    status: upstream.status,
    headers: responseHeaders
  })
}

type RouteContext = { params: { path: string[] } }

export function GET(request: Request, context: RouteContext) {
  return proxy(request, context.params.path)
}

export function POST(request: Request, context: RouteContext) {
  return proxy(request, context.params.path)
}

export function DELETE(request: Request, context: RouteContext) {
  return proxy(request, context.params.path)
}

export function PATCH(request: Request, context: RouteContext) {
  return proxy(request, context.params.path)
}
