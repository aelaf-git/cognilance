import { cardStyle, headerStyle, insetBoxStyle, useBrandColors } from "../theme";

type Props = {
  to?: string;
  subject?: string;
  body?: string;
  tone?: string;
  status?: string;
  gmail_message_id?: string | null;
  format_notes?: string;
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
  const colors = useBrandColors();
  const sent = status === "sent" || Boolean(gmail_message_id);
  const htmlBody = Boolean(body && looksLikeHtml(body));
  const inset = insetBoxStyle(colors);
  return (
    <div style={{ ...cardStyle(colors), maxWidth: 640 }}>
      <div style={headerStyle(colors)}>{sent ? "Email sent" : "Email draft"}</div>
      <div style={{ padding: "12px 16px", fontSize: 14 }}>
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
          <div style={{ marginBottom: 8, color: colors.muted, fontSize: 12 }}>Tone: {tone}</div>
        ) : null}
        {format_notes ? (
          <div style={{ marginBottom: 8, color: colors.muted, fontSize: 12 }}>
            Format: {format_notes}
          </div>
        ) : null}
        {body ? (
          htmlBody ? (
            <div style={inset} dangerouslySetInnerHTML={{ __html: sanitizeEmailHtml(body) }} />
          ) : (
            <pre style={{ ...inset, whiteSpace: "pre-wrap", fontFamily: "inherit" }}>{body}</pre>
          )
        ) : (
          <div style={{ color: colors.dim }}>No body returned.</div>
        )}
        {sent && gmail_message_id ? (
          <div style={{ marginTop: 8, fontSize: 12, color: colors.ember }}>
            Gmail message ID: {gmail_message_id}
          </div>
        ) : null}
      </div>
    </div>
  );
}
