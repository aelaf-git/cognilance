"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import {
  MAX_WAITLIST_USE_CASE,
  WAITLIST_AUDIENCES,
  WAITLIST_HEARD_FROM,
  WAITLIST_ROLES,
} from "@/lib/waitlist";
import styles from "./WaitlistForm.module.css";

type Status = "idle" | "loading" | "success" | "error";

export function WaitlistForm() {
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState("");
  const [audience, setAudience] = useState("");

  const companyRequired = audience === "Team / company";

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);

    const name = String(data.get("name") || "").trim();
    const email = String(data.get("email") || "").trim();
    const audienceValue = String(data.get("audience") || "").trim();
    const company = String(data.get("company") || "").trim();
    const role = String(data.get("role") || "").trim();
    const useCase = String(data.get("useCase") || "").trim();
    const heardFrom = String(data.get("heardFrom") || "").trim();

    setStatus("loading");
    setError("");

    try {
      const res = await fetch("/api/waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          email,
          audience: audienceValue,
          role,
          ...(company ? { company } : {}),
          ...(useCase ? { useCase } : {}),
          ...(heardFrom ? { heardFrom } : {}),
        }),
      });
      const payload = (await res.json().catch(() => ({}))) as {
        error?: string;
      };

      if (!res.ok) {
        setStatus("error");
        setError(payload.error || "Something went wrong. Please try again.");
        return;
      }

      form.reset();
      setAudience("");
      setStatus("success");
    } catch {
      setStatus("error");
      setError("Network error. Please try again.");
    }
  }

  if (status === "success") {
    return (
      <div className={styles.success} role="status">
        <p>You&apos;re on the list.</p>
        <p className={styles.successNext}>
          Access opens in waves. Watch this inbox for your invite.
        </p>
      </div>
    );
  }

  return (
    <form className={styles.form} onSubmit={onSubmit} noValidate>
      <div className={styles.pair}>
        <div className={styles.row}>
          <label htmlFor="waitlist-name">Name</label>
          <input
            id="waitlist-name"
            name="name"
            type="text"
            autoComplete="name"
            required
            maxLength={120}
            disabled={status === "loading"}
          />
        </div>
        <div className={styles.row}>
          <label htmlFor="waitlist-email">Email</label>
          <input
            id="waitlist-email"
            name="email"
            type="email"
            autoComplete="email"
            required
            maxLength={254}
            disabled={status === "loading"}
          />
        </div>
      </div>

      <div className={styles.pair}>
        <div className={styles.row}>
          <label htmlFor="waitlist-audience">I&apos;m joining as</label>
          <select
            id="waitlist-audience"
            name="audience"
            required
            value={audience}
            onChange={(event) => setAudience(event.target.value)}
            disabled={status === "loading"}
          >
            <option value="" disabled>
              Select one
            </option>
            {WAITLIST_AUDIENCES.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </div>
        <div className={styles.row}>
          <label htmlFor="waitlist-role">Role</label>
          <select
            id="waitlist-role"
            name="role"
            required
            defaultValue=""
            disabled={status === "loading"}
          >
            <option value="" disabled>
              Select role
            </option>
            {WAITLIST_ROLES.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className={styles.row}>
        <label htmlFor="waitlist-company">
          Company or team{" "}
          {companyRequired ? null : (
            <span className={styles.optional}>(optional)</span>
          )}
        </label>
        <input
          id="waitlist-company"
          name="company"
          type="text"
          autoComplete="organization"
          required={companyRequired}
          maxLength={120}
          placeholder={
            companyRequired
              ? "Company or team name"
              : "Optional if you have one"
          }
          disabled={status === "loading"}
        />
      </div>

      <div className={styles.row}>
        <label htmlFor="waitlist-use-case">
          What will you use Cognilance for?{" "}
          <span className={styles.optional}>(optional)</span>
        </label>
        <input
          id="waitlist-use-case"
          name="useCase"
          type="text"
          maxLength={MAX_WAITLIST_USE_CASE}
          placeholder="e.g. personal research, Friday reports, shared team work"
          disabled={status === "loading"}
        />
      </div>

      <div className={styles.row}>
        <label htmlFor="waitlist-heard-from">
          Where did you hear about us?{" "}
          <span className={styles.optional}>(optional)</span>
        </label>
        <select
          id="waitlist-heard-from"
          name="heardFrom"
          defaultValue=""
          disabled={status === "loading"}
        >
          <option value="">Select one</option>
          {WAITLIST_HEARD_FROM.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </div>

      {status === "error" && error ? (
        <p className={styles.error} role="alert">
          {error}
        </p>
      ) : null}

      <button
        type="submit"
        className={`btn btnPrimary ${styles.submit}`}
        disabled={status === "loading"}
      >
        <span className="btnText">
          <span>{status === "loading" ? "Joining…" : "Join the waitlist"}</span>
          <span aria-hidden="true">
            {status === "loading" ? "Joining…" : "Join the waitlist"}
          </span>
        </span>
      </button>

      <p className={styles.privacy}>
        We use these details only to invite you and prioritize access.{" "}
        <Link href="/privacy">Privacy</Link>
      </p>
    </form>
  );
}
