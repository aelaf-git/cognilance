import { NextResponse } from "next/server";
import { getDb } from "@/lib/mongodb";
import {
  isWaitlistAudience,
  isWaitlistHeardFrom,
  isWaitlistRole,
  MAX_WAITLIST_USE_CASE,
  type WaitlistAudience,
  type WaitlistHeardFrom,
  type WaitlistRole,
} from "@/lib/waitlist";

export const runtime = "nodejs";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MAX_NAME = 120;
const MAX_EMAIL = 254;
const MAX_COMPANY = 120;

type WaitlistBody = {
  name?: unknown;
  email?: unknown;
  audience?: unknown;
  company?: unknown;
  role?: unknown;
  useCase?: unknown;
  heardFrom?: unknown;
};

function asTrimmed(value: unknown, max: number): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (!trimmed || trimmed.length > max) return null;
  return trimmed;
}

let indexReady: Promise<void> | null = null;

async function ensureEmailIndex() {
  if (!indexReady) {
    indexReady = (async () => {
      const db = await getDb();
      await db.collection("waitlist").createIndex({ email: 1 }, { unique: true });
    })().catch((err) => {
      indexReady = null;
      throw err;
    });
  }
  await indexReady;
}

export async function POST(request: Request) {
  if (!process.env.MONGODB_URI) {
    return NextResponse.json(
      { error: "Waitlist is not configured." },
      { status: 503 }
    );
  }

  let body: WaitlistBody;
  try {
    body = (await request.json()) as WaitlistBody;
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const name = asTrimmed(body.name, MAX_NAME);
  const emailRaw = asTrimmed(body.email, MAX_EMAIL);
  const audienceRaw =
    typeof body.audience === "string" ? body.audience.trim() : "";
  const company =
    body.company === undefined || body.company === null || body.company === ""
      ? undefined
      : asTrimmed(body.company, MAX_COMPANY);
  const roleRaw = typeof body.role === "string" ? body.role.trim() : "";
  const useCase =
    body.useCase === undefined || body.useCase === null || body.useCase === ""
      ? undefined
      : asTrimmed(body.useCase, MAX_WAITLIST_USE_CASE);
  const heardFromRaw =
    body.heardFrom === undefined ||
    body.heardFrom === null ||
    body.heardFrom === ""
      ? undefined
      : typeof body.heardFrom === "string"
        ? body.heardFrom.trim()
        : "";

  if (!name || !emailRaw) {
    return NextResponse.json(
      { error: "Name and email are required." },
      { status: 400 }
    );
  }

  if (!audienceRaw || !isWaitlistAudience(audienceRaw)) {
    return NextResponse.json(
      { error: "Please choose whether you are joining as an individual or a team." },
      { status: 400 }
    );
  }

  const audience: WaitlistAudience = audienceRaw;

  if (!roleRaw || !isWaitlistRole(roleRaw)) {
    return NextResponse.json(
      { error: "Please select a valid role." },
      { status: 400 }
    );
  }

  const role: WaitlistRole = roleRaw;

  if (audience === "Team / company" && !company) {
    return NextResponse.json(
      { error: "Company or team name is required when joining as a team." },
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
      { error: "Company or team name is too long." },
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
    body.useCase !== undefined &&
    body.useCase !== null &&
    body.useCase !== "" &&
    !useCase
  ) {
    return NextResponse.json(
      { error: "Use case is too long." },
      { status: 400 }
    );
  }

  let heardFrom: WaitlistHeardFrom | undefined;
  if (heardFromRaw !== undefined) {
    if (!heardFromRaw || !isWaitlistHeardFrom(heardFromRaw)) {
      return NextResponse.json(
        { error: "Please select a valid referral source." },
        { status: 400 }
      );
    }
    heardFrom = heardFromRaw;
  }

  try {
    await ensureEmailIndex();
    const db = await getDb();
    await db.collection("waitlist").insertOne({
      name,
      email,
      audience,
      role,
      ...(company ? { company } : {}),
      ...(useCase ? { useCase } : {}),
      ...(heardFrom ? { heardFrom } : {}),
      source: "waitlist",
      createdAt: new Date(),
    });
    return NextResponse.json({ ok: true });
  } catch (err) {
    const code =
      err && typeof err === "object" && "code" in err
        ? (err as { code?: number }).code
        : undefined;
    if (code === 11000) {
      return NextResponse.json(
        { error: "You're already on the waitlist." },
        { status: 409 }
      );
    }
    console.error("Waitlist insert error:", err);
    return NextResponse.json(
      { error: "Could not join the waitlist. Please try again." },
      { status: 502 }
    );
  }
}
