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
    upstream = await fetch(`${COORDINATOR_URL}/docx/${id}/file`, {
      headers: { cookie: request.headers.get("cookie") ?? "" }
    })
  } catch {
    return Response.json(
      { error: "Cognilance coordinator is not running." },
      { status: 502 }
    )
  }

  if (!upstream.ok || !upstream.body) {
    return Response.json({ error: "Document not found." }, { status: upstream.status || 404 })
  }

  const headers = new Headers()
  const type = upstream.headers.get("content-type")
  if (type) headers.set("Content-Type", type)
  const disposition = upstream.headers.get("content-disposition")
  if (disposition) headers.set("Content-Disposition", disposition)
  return new Response(upstream.body, { status: 200, headers })
}
