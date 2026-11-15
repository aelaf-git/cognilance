export const dynamic = "force-dynamic"
export const runtime = "nodejs"

const COORDINATOR_URL =
  process.env.COGNILANCE_COORDINATOR_URL || "http://127.0.0.1:8200"

export async function GET(
  request: Request,
  { params }: { params: { id: string } }
) {
  const id = params.id
  if (!/^doc_[a-f0-9]{12}$/.test(id)) {
    return Response.json({ error: "Unknown document." }, { status: 404 })
  }

  let upstream: Response
  try {
    upstream = await fetch(`${COORDINATOR_URL}/docx/${id}`, {
      headers: { cookie: request.headers.get("cookie") ?? "" },
      cache: "no-store"
    })
  } catch {
    return Response.json(
      { error: "Cognilance coordinator is not running." },
      { status: 502 }
    )
  }

  const payload = await upstream.json().catch(() => ({}))
  if (!upstream.ok) {
    return Response.json(
      { error: payload.detail || payload.error || "Document not found." },
      { status: upstream.status || 404 }
    )
  }
  return Response.json(payload)
}
