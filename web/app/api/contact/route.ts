import { NextResponse } from "next/server";
import { Resend } from "resend";
import { getDb } from "@/lib/mongodb";
import { EMAIL } from "@/lib/site";

export const runtime = "nodejs";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MAX_NAME = 120;
const MAX_EMAIL = 254;
const MAX_COMPANY = 120;
const MAX_MESSAGE = 5000;

type ContactBody = {
  name?: unknown;
  email?: unknown;
  message?: unknown;
  company?: unknown;
};

function asTrimmed(value: unknown, max: number): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (!trimmed || trimmed.length > max) return null;
  return trimmed;
}

export async function POST(request: Request) {
  if (!process.env.MONGODB_URI) {
    return NextResponse.json(
      { error: "Contact is not configured." },
      { status: 503 }
    );
  }

  let body: ContactBody;
  try {
    body = (await request.json()) as ContactBody;
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const name = asTrimmed(body.name, MAX_NAME);
  const emailRaw = asTrimmed(body.email, MAX_EMAIL);
  const message = asTrimmed(body.message, MAX_MESSAGE);
  const company =
    body.company === undefined || body.company === null || body.company === ""
      ? undefined
      : asTrimmed(body.company, MAX_COMPANY);

  if (!name || !emailRaw || !message) {
    return NextResponse.json(
      { error: "Name, email, and message are required." },
      { status: 400 }
    );
  }

  const email = emailRaw.toLowerCase();
  if (!EMAIL_RE.test(email)) {
    return NextResponse.json(
      { error: "Please enter a valid email address." },
      { status: 400 }
    );
  }

  if (
    body.company !== undefined &&
    body.company !== null &&
    body.company !== "" &&
    !company
  ) {
    return NextResponse.json(
      { error: "Company name is too long." },
      { status: 400 }
    );
  }

  const apiKey = process.env.RESEND_API_KEY?.trim();
  let emailDelivered = false;

  if (apiKey) {
    const from =
      process.env.CONTACT_FROM?.trim() ||
      "Cognilance <contact@cognilanceai.com>";
    const to = process.env.CONTACT_TO?.trim() || EMAIL;
    const lines = [
      `Name: ${name}`,
      `Email: ${email}`,
      company ? `Company: ${company}` : null,
      "",
      message,
    ].filter((line): line is string => line !== null);

    try {
      const resend = new Resend(apiKey);
      const { error } = await resend.emails.send({
        from,
        to: [to],
        replyTo: email,
        subject: `Contact: ${name}`,
        text: lines.join("\n"),
      });

      if (error) {
        console.error("Resend contact error:", error);
        return NextResponse.json(
          { error: "Could not send your message. Please try again." },
          { status: 502 }
        );
      }
      emailDelivered = true;
    } catch (err) {
      console.error("Resend contact exception:", err);
      return NextResponse.json(
        { error: "Could not send your message. Please try again." },
        { status: 502 }
      );
    }
  }

  try {
    const db = await getDb();
    await db.collection("contact").insertOne({
      name,
      email,
      ...(company ? { company } : {}),
      message,
      source: "contact",
      emailDelivered,
      createdAt: new Date(),
    });
    return NextResponse.json({ ok: true });
  } catch (err) {
    console.error("Contact insert error:", err);
    return NextResponse.json(
      { error: "Could not send your message. Please try again." },
      { status: 502 }
    );
  }
}
