export const dynamic = "force-dynamic"
export const runtime = "nodejs"

const ORCHESTRATOR_URL =
  process.env.COGNILANCE_ORCHESTRATOR_URL || "http://127.0.0.1:8200"

export async function POST(request: Request) {
  const payload = await request.json()
  let upstream: Response
  try {
    upstream = await fetch(`${ORCHESTRATOR_URL}/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        cookie: request.headers.get("cookie") ?? ""
      },
      body: JSON.stringify({
        text: payload?.text,
        conversation_id: payload?.conversation_id
      })
    })
  } catch {
    return Response.json(
      { error: "Cognilance orchestrator is not running." },
      { status: 502 }
    )
  }

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
