"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import styles from "./SiteHeader.module.css";

const WAITLIST =
  "https://docs.google.com/forms/d/e/1FAIpQLScV72qv_wHi7nWeNXm76kjI9lYYKV740lULDBs6nWH0xuALnQ/viewform?usp=publish-editor";

const LINKS = [
  { href: "#product", label: "Product" },
  { href: "#how", label: "How it works" },
  { href: "#pricing", label: "Pricing" },
  { href: "#developers", label: "For Developers" },
  { href: "#founders", label: "Founders" },
];

export function SiteHeader() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  const close = () => setOpen(false);

  return (
    <header className={styles.header}>
      <div className={`container ${styles.inner}`}>
        <a href="#top" className={styles.brand} onClick={close}>
          <Image
            src="/brand/icon.png"
            alt=""
            width={44}
            height={44}
            className={styles.icon}
            priority
          />
          <Image
            src="/brand/logo.png"
            alt="Cognilance"
            width={200}
            height={26}
            className={styles.logo}
            priority
          />
        </a>

        <nav className={styles.nav} aria-label="Primary">
          {LINKS.map((link) => (
            <a key={link.href} href={link.href}>
              {link.label}
            </a>
          ))}
        </nav>

        <div className={styles.right}>
          <a
            href={WAITLIST}
            className={`btn btnPrimary ${styles.cta}`}
            target="_blank"
            rel="noreferrer"
          >
            <span className={styles.ctaFull}>Join the waitlist</span>
            <span className={styles.ctaShort}>Waitlist</span>
          </a>
          <button
            type="button"
            className={styles.menuBtn}
            aria-expanded={open}
            aria-controls="mobile-nav"
            aria-label={open ? "Close menu" : "Open menu"}
            onClick={() => setOpen((v) => !v)}
          >
            <span className={open ? styles.menuClose : styles.menuBars} />
          </button>
        </div>
      </div>

      <div
        id="mobile-nav"
        className={`${styles.mobilePanel} ${open ? styles.mobileOpen : ""}`}
      >
        <nav className={styles.mobileNav} aria-label="Mobile">
          {LINKS.map((link) => (
            <a key={link.href} href={link.href} onClick={close}>
              {link.label}
            </a>
          ))}
          <a
            href={WAITLIST}
            className={`btn btnPrimary ${styles.mobileCta}`}
            target="_blank"
            rel="noreferrer"
            onClick={close}
          >
            Join the waitlist
          </a>
        </nav>
      </div>
    </header>
  );
}
