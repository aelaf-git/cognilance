import Image from "next/image";
import { Button } from "./Button";
import { HeroFibers } from "./HeroFibers";
import { WAITLIST } from "@/lib/site";
import styles from "./Hero.module.css";

const stats = [
  { value: "1", label: "Shared conversation" },
  { value: "7+", label: "Tools connected" },
  { value: "Days", label: "Long-running work" },
  { value: "You", label: "Approve what matters" },
];

const partners = [
  {
    name: "Ethiopian Artificial Intelligence Institute",
    host: "aii.et",
    href: "https://aii.et/Home",
    src: "/brand/partners/aii.png",
    width: 36,
    height: 36,
  },
  {
    name: "Dev3pack",
    host: "dev3pack.xyz",
    href: "https://dev3pack.xyz",
    src: "/brand/partners/dev3pack.png",
    width: 36,
    height: 48,
  },
];

export function Hero() {
  return (
    <section id="top" className={styles.hero}>
      <div className={styles.stage}>
        <div className={styles.fibers} aria-hidden="true">
          <HeroFibers />
        </div>

        <div className={styles.grid}>
          <div className={styles.copy}>
            <div className={styles.trust}>
              <span className={styles.trustLabel}>Backed by</span>
              <div className={styles.trustLogos}>
                {partners.map((partner, i) => (
                  <span key={partner.href} className={styles.trustItem}>
                    {i > 0 ? (
                      <span className={styles.trustRule} aria-hidden="true" />
                    ) : null}
                    <a
                      href={partner.href}
                      target="_blank"
                      rel="noreferrer"
                      className={styles.trustLogo}
                      aria-label={`${partner.name} (${partner.host})`}
                    >
                      <Image
                        src={partner.src}
                        alt=""
                        width={partner.width}
                        height={partner.height}
                        className={styles.trustMark}
                      />
                      <span className={styles.trustMeta}>
                        <strong>{partner.name}</strong>
                        <span>{partner.host}</span>
                      </span>
                    </a>
                  </span>
                ))}
              </div>
            </div>

            <h1>
              The AI Assistant{" "}
              <span className={styles.accent}>for Teams</span>
            </h1>
            <p className={styles.lead}>
              Shared agents, long running work, and improvement with human
              approval. Built for teams, and strong for a single person too.
            </p>
            <div className={styles.actions}>
              <Button href={WAITLIST} hoverText="Join the waitlist →">
                Join the waitlist →
              </Button>
              <Button href="/#how" variant="ghost">
                See how it works
              </Button>
            </div>
          </div>
        </div>

        <div className={styles.stats}>
          {stats.map((stat) => (
            <div key={stat.label} className={styles.stat}>
              <strong>{stat.value}</strong>
              <span>{stat.label}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
