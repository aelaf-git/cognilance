import Image from "next/image";
import Link from "next/link";
import styles from "./Footer.module.css";

const WAITLIST =
  "https://docs.google.com/forms/d/e/1FAIpQLScV72qv_wHi7nWeNXm76kjI9lYYKV740lULDBs6nWH0xuALnQ/viewform?usp=publish-editor";

const OFFICE_MAPS = "https://maps.app.goo.gl/3CwxEVPkf9WyFR7L8";
const EMAIL = "cognilance@gmail.com";
const PHONE = "+251 964 336 078";
const PHONE_TEL = "+251964336078";

const columns = [
  {
    title: "Product",
    links: [
      { href: "/#product", label: "Overview" },
      { href: "/#how", label: "How it works" },
      { href: "/#use-cases", label: "Use cases" },
      { href: "/#pricing", label: "Pricing" },
    ],
  },
  {
    title: "Company",
    links: [
      { href: "/#founders", label: "Founders" },
      { href: "/#social-proof", label: "Backers" },
    ],
  },
  {
    title: "Resources",
    links: [
      { href: "/developers", label: "Developers" },
    ],
  },
  {
    title: "Get started",
    links: [
      { href: WAITLIST, label: "Join the waitlist", external: true },
      { href: "/#pricing", label: "Pricing" },
      { href: "/developers", label: "Build agents" },
    ],
  },
];

export function Footer() {
  return (
    <footer className={styles.footer}>
      <div className={styles.shell}>
        <div className={styles.top}>
          <div className={styles.brandCol}>
            <Link href="/" className={styles.brand}>
              <Image
                src="/brand/icon.png"
                alt=""
                width={72}
                height={72}
                className={styles.icon}
              />
              <span className={styles.brandName}>Cognilance</span>
            </Link>
            <p className={styles.blurb}>
              Automate without babysitting. Hire specialist agents and ship
              work that finishes itself.
            </p>
            <div className={styles.contact}>
              <p className={styles.contactTitle}>Contact</p>
              <a
                href={OFFICE_MAPS}
                className={styles.contactLine}
                target="_blank"
                rel="noreferrer"
              >
                AI Startup Center, 3rd floor
              </a>
              <a href={`mailto:${EMAIL}`} className={styles.contactLine}>
                {EMAIL}
              </a>
              <a href={`tel:${PHONE_TEL}`} className={styles.contactLine}>
                {PHONE}
              </a>
            </div>
            <a
              href={WAITLIST}
              className={`btn btnPrimary ${styles.cta}`}
              target="_blank"
              rel="noreferrer"
            >
              Join the waitlist
            </a>
          </div>

          <nav className={styles.columns} aria-label="Footer">
            {columns.map((column) => (
              <div key={column.title} className={styles.column}>
                <p className={styles.columnTitle}>{column.title}</p>
                <ul className={styles.linkList}>
                  {column.links.map((link) => (
                    <li key={link.label}>
                      {"external" in link && link.external ? (
                        <a href={link.href} target="_blank" rel="noreferrer">
                          {link.label}
                        </a>
                      ) : link.href.includes("#") ? (
                        <a href={link.href}>{link.label}</a>
                      ) : (
                        <Link href={link.href}>{link.label}</Link>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </nav>
        </div>

        <div className={styles.divider} />

        <div className={styles.legal}>
          <p className={styles.copy}>
            © {new Date().getFullYear()} Cognilance. All rights reserved.
          </p>
        </div>

        <div className={styles.wordmarkWrap}>
          <Image
            src="/brand/logo.png"
            alt="Cognilance"
            width={1276}
            height={168}
            className={styles.wordmark}
            priority={false}
          />
        </div>
      </div>
    </footer>
  );
}
