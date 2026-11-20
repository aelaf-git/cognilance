export const dynamic = "force-dynamic"
export const runtime = "nodejs"

const COORDINATOR_URL =
  process.env.COGNILANCE_COORDINATOR_URL || "http://127.0.0.1:8200"

function streamResponse(upstream: Response) {
  const headers = new Headers({
    "Content-Type":
      upstream.headers.get("content-type") || "text/event-stream",
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no"
  })
  const setCookies =
    typeof upstream.headers.getSetCookie === "function"
      ? upstream.headers.getSetCookie()
      : []
  for (const cookie of setCookies) {
    headers.append("set-cookie", cookie)
  }
  return new Response(upstream.body, {
    status: upstream.status,
    headers
  })
}

export async function GET(request: Request) {
  const url = new URL(request.url)
  const upstreamUrl = new URL(`${COORDINATOR_URL}/chat/stream`)
  url.searchParams.forEach((value, key) => {
    upstreamUrl.searchParams.set(key, value)
  })
  let upstream: Response
  try {
    upstream = await fetch(upstreamUrl, {
      headers: {
        Accept: "text/event-stream",
        cookie: request.headers.get("cookie") ?? ""
      }
    })
  } catch {
    return Response.json(
      { error: "Cognilance coordinator is not running." },
      { status: 502 }
    )
  }
  return streamResponse(upstream)
}

export async function POST(request: Request) {
  const payload = await request.json()
  let upstream: Response
  try {
    upstream = await fetch(`${COORDINATOR_URL}/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        cookie: request.headers.get("cookie") ?? ""
      },
      body: JSON.stringify({
        text: payload?.text,
        conversation_id: payload?.conversation_id,
        regenerate: payload?.regenerate === true
      })
    })
  } catch {
    return Response.json(
      { error: "Cognilance coordinator is not running." },
      { status: 502 }
    )
  }
  return streamResponse(upstream)
}
