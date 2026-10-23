"use client";

import { FormEvent, useState } from "react";
import styles from "./Contact.module.css";

type Status = "idle" | "loading" | "success" | "error";

export function ContactForm() {
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState("");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);

    const name = String(data.get("name") || "").trim();
    const email = String(data.get("email") || "").trim();
    const company = String(data.get("company") || "").trim();
    const message = String(data.get("message") || "").trim();

    setStatus("loading");
    setError("");

    try {
      const res = await fetch("/api/contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          email,
          message,
          ...(company ? { company } : {}),
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
      setStatus("success");
    } catch {
      setStatus("error");
      setError("Network error. Please try again.");
    }
  }

  if (status === "success") {
    return (
      <p className={styles.formSuccess} role="status">
        Thanks. Your message was sent. We will get back to you soon.
      </p>
    );
  }

  return (
    <form className={styles.form} onSubmit={onSubmit} noValidate>
      <div className={styles.formPair}>
        <div className={styles.formRow}>
          <label htmlFor="contact-name">Name</label>
          <input
            id="contact-name"
            name="name"
            type="text"
            autoComplete="name"
            required
            maxLength={120}
            disabled={status === "loading"}
          />
        </div>
        <div className={styles.formRow}>
          <label htmlFor="contact-email">Email</label>
          <input
            id="contact-email"
            name="email"
            type="email"
            autoComplete="email"
            required
            maxLength={254}
            disabled={status === "loading"}
          />
        </div>
      </div>
      <div className={styles.formRow}>
        <label htmlFor="contact-company">
          Company <span className={styles.optional}>(optional)</span>
        </label>
        <input
          id="contact-company"
          name="company"
          type="text"
          autoComplete="organization"
          maxLength={120}
          disabled={status === "loading"}
        />
      </div>
      <div className={styles.formRow}>
        <label htmlFor="contact-message">Message</label>
        <textarea
          id="contact-message"
          name="message"
          required
          rows={5}
          maxLength={5000}
          disabled={status === "loading"}
        />
      </div>

      {status === "error" && error ? (
        <p className={styles.formError} role="alert">
          {error}
        </p>
      ) : null}

      <button
        type="submit"
        className={`btn btnPrimary ${styles.submit}`}
        disabled={status === "loading"}
      >
        <span className="btnText">
          <span>{status === "loading" ? "Sending…" : "Send message"}</span>
          <span aria-hidden="true">
            {status === "loading" ? "Sending…" : "Send message"}
          </span>
        </span>
      </button>
    </form>
  );
}
