import Link from "next/link";
import { Button } from "./Button";
import {
  FOOTER_COLUMNS,
  LEGAL_LINKS,
  WAITLIST,
} from "@/lib/site";
import styles from "./Footer.module.css";

function FooterLink({
  href,
  label,
  external,
}: {
  href: string;
  label: string;
  external?: boolean;
}) {
  if (external || href.startsWith("http") || href.startsWith("mailto:")) {
    return (
      <a
        href={href}
        {...(href.startsWith("http")
          ? { target: "_blank", rel: "noreferrer" }
          : {})}
      >
        {label}
      </a>
    );
  }

  if (href.startsWith("/") && !href.includes("#")) {
    return <Link href={href}>{label}</Link>;
  }

  return <a href={href}>{label}</a>;
}

export function Footer() {
  return (
    <footer id="waitlist" className={styles.footer}>
      <div className={styles.shell}>
        <div className={styles.ctaCard}>
          <div className={styles.ctaCopy}>
            <h2>Join the waitlist</h2>
            <p>
              Opening access in waves for people and teams ready to work with
              shared agents.
            </p>
          </div>
          <div className={styles.ctaActions}>
            <Button href={WAITLIST} hoverText="Join the waitlist →">
              Join the waitlist →
            </Button>
            <Button href="/#how" variant="ghost">
              See how it works
            </Button>
          </div>
        </div>

        <div className={styles.columns}>
          {FOOTER_COLUMNS.map((col) => (
            <div key={col.title} className={styles.column}>
              <h3>{col.title}</h3>
              <ul>
                {col.links.map((link) => (
                  <li key={link.href + link.label}>
                    <FooterLink
                      href={link.href}
                      label={link.label}
                      external={
                        "external" in link ? Boolean(link.external) : false
                      }
                    />
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className={styles.bottom}>
          <div className={styles.brandLegal}>
            <p>© {new Date().getFullYear()} Cognilance. All rights reserved.</p>
            <p>The AI Assistant for Teams.</p>
          </div>
          <nav aria-label="Legal documents" className={styles.legalNav}>
            {LEGAL_LINKS.map((link) => (
              <Link key={link.href} href={link.href}>
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
      </div>
    </footer>
  );
}
