"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState, type Ref } from "react";
import { Button } from "./Button";
import { NAV_LINKS, WAITLIST } from "@/lib/site";
import styles from "./SiteHeader.module.css";

function NavLinks({
  onClick,
  className,
}: {
  onClick?: () => void;
  className?: string;
}) {
  return (
    <nav className={className} aria-label="Primary">
      {NAV_LINKS.map((link) =>
        link.href.startsWith("/") && !link.href.includes("#") ? (
          <Link key={link.href} href={link.href} onClick={onClick}>
            {link.label}
          </Link>
        ) : (
          <a key={link.href} href={link.href} onClick={onClick}>
            {link.label}
          </a>
        ),
      )}
    </nav>
  );
}

function Brand({ onClick }: { onClick?: () => void }) {
  return (
    <Link href="/" className={styles.brand} onClick={onClick}>
      <Image
        src="/brand/Cognilance-Logo.png"
        alt="Cognilance"
        width={40}
        height={40}
        className={styles.icon}
        priority
      />
      <span className={styles.brandName}>Cognilance</span>
    </Link>
  );
}

function MenuToggle({
  open,
  onClick,
  label,
}: {
  open: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      className={`${styles.menuBtn} ${open ? styles.menuOpen : ""}`}
      aria-expanded={open}
      aria-controls="mobile-nav"
      aria-label={label}
      onClick={onClick}
    >
      <span />
      <span />
      <span />
    </button>
  );
}

function Bar({
  variant,
  scrolled,
  open,
  onToggle,
  solid,
  light,
  barRef,
}: {
  variant: "static" | "fixed";
  scrolled: boolean;
  open: boolean;
  onToggle: () => void;
  solid?: boolean;
  light?: boolean;
  barRef?: Ref<HTMLElement>;
}) {
  const classes = [
    styles.header,
    variant === "static" ? styles.static : styles.fixed,
    light ? styles.light : "",
    solid ? styles.solid : "",
    !solid && variant === "fixed" && scrolled && !open ? styles.visible : "",
    open ? styles.hidden : "",
  ]
    .filter(Boolean)
    .join(" ");

  const ctaVariant = light ? "primary" : "ghost";

  return (
    <header
      ref={barRef}
      className={classes}
      aria-hidden={
        variant === "fixed" && !solid ? !scrolled || open : open
      }
    >
      <div className={styles.shell}>
        <div className={styles.inner}>
          <Brand />
          <NavLinks className={styles.nav} />
          <div className={styles.right}>
            <Button
              href={WAITLIST}
              variant={ctaVariant}
              className={styles.cta}
              hoverText="Join the waitlist"
            >
              Join the waitlist
            </Button>
            <MenuToggle
              open={open}
              onClick={onToggle}
              label={open ? "Close menu" : "Open menu"}
            />
          </div>
        </div>
      </div>
    </header>
  );
}

export function SiteHeader({ overlay = false }: { overlay?: boolean }) {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const barRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 300);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    const el = barRef.current;
    if (!el) return;
    const apply = () => {
      const h = Math.ceil(el.getBoundingClientRect().height);
      document.documentElement.style.setProperty("--header-height", `${h}px`);
    };
    apply();
    const ro = new ResizeObserver(apply);
    ro.observe(el);
    return () => ro.disconnect();
  }, [overlay]);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  const close = () => setOpen(false);
  const onToggle = () => setOpen((v) => !v);

  return (
    <>
      <Bar
        variant={overlay ? "static" : "fixed"}
        scrolled={overlay ? scrolled : true}
        open={open}
        onToggle={onToggle}
        solid={!overlay}
        light={overlay}
        barRef={barRef}
      />
      {overlay ? (
        <Bar
          variant="fixed"
          scrolled={scrolled}
          open={open}
          onToggle={onToggle}
        />
      ) : null}

      <div
        id="mobile-nav"
        className={`${styles.drawer} ${open ? styles.drawerOpen : ""}`}
      >
        <div
          className={styles.drawerBackdrop}
          onClick={close}
          aria-hidden="true"
        />
        <aside
          className={styles.drawerSheet}
          role="dialog"
          aria-modal="true"
          aria-label="Menu"
        >
          <div className={styles.drawerTop}>
            <Brand onClick={close} />
            <MenuToggle open onClick={close} label="Close menu" />
          </div>
          <NavLinks className={styles.drawerNav} onClick={close} />
          <Button
            href={WAITLIST}
            variant="ghost"
            className={styles.drawerCta}
            onClick={close}
            hoverText="Join the waitlist"
          >
            Join the waitlist
          </Button>
        </aside>
      </div>
    </>
  );
}
