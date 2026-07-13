import { CSSProperties } from "react";

type Props = {
  to?: string;
  subject?: string;
  body?: string;
  tone?: string;
  status?: string;
  gmail_message_id?: string | null;
  format_notes?: string;
};

const card: CSSProperties = {
  width: "100%",
  maxWidth: 640,
  border: "1px solid #e5e7eb",
  borderRadius: 12,
  overflow: "hidden",
  fontFamily: "ui-sans-serif, system-ui, sans-serif",
  background: "#fff",
};

const header: CSSProperties = {
  background: "linear-gradient(90deg,#0f766e,#14b8a6)",
  color: "#fff",
  padding: "12px 16px",
  fontWeight: 600,
};

function looksLikeHtml(body: string): boolean {
  const t = body.trim().toLowerCase();
  if (!t.includes("<")) return false;
  return (
    /<(p|br|div|span|h[1-3]|ul|ol|li|a|strong|em|b|i)\b/.test(t) ||
    t.includes("font-family") ||
    t.includes("style=")
  );
}

/** Strip script/iframe/on* handlers from agent HTML fragments for safe preview. */
function sanitizeEmailHtml(html: string): string {
  return html
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, "")
    .replace(/<iframe\b[^<]*(?:(?!<\/iframe>)<[^<]*)*<\/iframe>/gi, "")
    .replace(/\son\w+\s*=\s*(['"]).*?\1/gi, "")
    .replace(/\son\w+\s*=\s*[^\s>]+/gi, "")
    .replace(/javascript:/gi, "");
}

export default function EmailDraft({
  to,
  subject,
  body,
  tone,
  status,
  gmail_message_id,
  format_notes,
}: Props) {
  const sent = status === "sent" || Boolean(gmail_message_id);
  const htmlBody = Boolean(body && looksLikeHtml(body));
  return (
    <div style={card}>
      <div style={header}>{sent ? "Email sent" : "Email draft"}</div>
      <div style={{ padding: "12px 16px", color: "#374151", fontSize: 14 }}>
        {to ? (
          <div style={{ marginBottom: 8 }}>
            <strong>To:</strong> {to}
          </div>
        ) : null}
        {subject ? (
          <div style={{ marginBottom: 8 }}>
            <strong>Subject:</strong> {subject}
          </div>
        ) : null}
        {tone ? (
          <div style={{ marginBottom: 8, color: "#6b7280", fontSize: 12 }}>
            Tone: {tone}
          </div>
        ) : null}
        {format_notes ? (
          <div style={{ marginBottom: 8, color: "#6b7280", fontSize: 12 }}>
            Format: {format_notes}
          </div>
        ) : null}
        {body ? (
          htmlBody ? (
            <div
              style={{
                margin: 0,
                padding: 12,
                background: "#f9fafb",
                borderRadius: 8,
                border: "1px solid #f1f5f9",
                lineHeight: 1.5,
                overflow: "auto",
              }}
              dangerouslySetInnerHTML={{ __html: sanitizeEmailHtml(body) }}
            />
          ) : (
            <pre
              style={{
                whiteSpace: "pre-wrap",
                fontFamily: "inherit",
                margin: 0,
                padding: 12,
                background: "#f9fafb",
                borderRadius: 8,
                border: "1px solid #f1f5f9",
              }}
            >
              {body}
            </pre>
          )
        ) : (
          <div style={{ color: "#9ca3af" }}>No body returned.</div>
        )}
        {sent && gmail_message_id ? (
          <div style={{ marginTop: 8, fontSize: 12, color: "#059669" }}>
            Gmail message ID: {gmail_message_id}
          </div>
        ) : null}
      </div>
    </div>
  );
}
