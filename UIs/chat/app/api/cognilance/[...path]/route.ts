export const dynamic = "force-dynamic"
export const runtime = "nodejs"

const ORCHESTRATOR_URL =
  process.env.COGNILANCE_ORCHESTRATOR_URL || "http://127.0.0.1:8200"

function allowed(method: string, path: string) {
  return (
    (method === "GET" && path === "conversations") ||
    (method === "POST" && path === "conversations") ||
    (method === "GET" && path === "integrations/list") ||
    /^GET conversations\/[^/]+$/.test(`${method} ${path}`) ||
    /^DELETE conversations\/[^/]+$/.test(`${method} ${path}`) ||
    /^GET conversations\/[^/]+\/sessions$/.test(`${method} ${path}`) ||
    /^GET integrations\/[^/]+\/connect$/.test(`${method} ${path}`) ||
    /^POST integrations\/[^/]+\/disconnect$/.test(`${method} ${path}`)
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
    upstream = await fetch(`${ORCHESTRATOR_URL}/${joined}`, {
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
      { error: "Cognilance orchestrator is not running." },
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
