"use client";

import { FormEvent, useState } from "react";
import { Reveal } from "./Reveal";
import styles from "./Waitlist.module.css";

type Status = "idle" | "loading" | "done" | "error";

export function Waitlist() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState("");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = email.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) {
      setStatus("error");
      setMessage("Enter a valid work email.");
      return;
    }

    setStatus("loading");
    setMessage("");
    const endpoint = process.env.NEXT_PUBLIC_WAITLIST_ENDPOINT;

    try {
      if (endpoint) {
        const res = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: trimmed }),
        });
        if (!res.ok) throw new Error("Request failed");
      }
      setStatus("done");
      setMessage("You're on the list. We'll reach out as beta seats open.");
      setEmail("");
    } catch {
      setStatus("error");
      setMessage("Something went wrong. Try again in a moment.");
    }
  }

  return (
    <section className={`section ${styles.wrap}`} id="waitlist">
      <div className="container">
        <Reveal>
          <p className="eyebrow">Beta access</p>
          <h2>Build with Cognilance while it&apos;s early</h2>
          <p className="lead">
            We&apos;re onboarding teams who need production-grade multi-agent
            orchestration — not another demo sandbox. Join the beta waitlist.
          </p>
        </Reveal>
        <Reveal delayMs={120}>
          <form className={styles.form} onSubmit={onSubmit} noValidate>
            <label className={styles.label} htmlFor="beta-email">
              Work email
            </label>
            <div className={styles.row}>
              <input
                id="beta-email"
                type="email"
                name="email"
                autoComplete="email"
                placeholder="you@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={status === "loading" || status === "done"}
                required
              />
              <button
                type="submit"
                className="btn btnPrimary"
                disabled={status === "loading" || status === "done"}
              >
                {status === "loading"
                  ? "Joining…"
                  : status === "done"
                    ? "Joined"
                    : "Join the beta"}
              </button>
            </div>
            {message ? (
              <p
                className={
                  status === "error" ? styles.error : styles.success
                }
                role="status"
              >
                {message}
              </p>
            ) : (
              <p className={styles.hint}>
                Limited beta · No spam · Product updates only
              </p>
            )}
          </form>
        </Reveal>
      </div>
    </section>
  );
}
