import { Reveal } from "./Reveal";
import styles from "./Pricing.module.css";

const WAITLIST =
  "https://docs.google.com/forms/d/e/1FAIpQLScV72qv_wHi7nWeNXm76kjI9lYYKV740lULDBs6nWH0xuALnQ/viewform?usp=publish-editor";

const tiers = [
  {
    name: "Free",
    price: "$0",
    detail: "Join the waitlist for early access to Cognilance.",
    points: [
      "Access free agents",
      "Limited tokens",
      "Core orchestrator chat",
      "Community support",
    ],
    cta: "Join the waitlist",
    href: WAITLIST,
    external: true,
    featured: true,
    comingSoon: false,
  },
  {
    name: "Pro",
    price: "$ --",
    detail: "For operators who need more capacity and specialist agents.",
    points: [
      "Higher token limits",
      "Hire marketplace agents",
      "Validation stage included",
      "Priority support",
    ],
    cta: "Coming soon",
    href: "#pricing",
    external: false,
    featured: false,
    comingSoon: true,
  },
  {
    name: "Expert",
    price: "$ --",
    detail: "Advanced limits and tooling for heavy production workloads.",
    points: [
      "Expanded token pool",
      "Advanced agent access",
      "Faster orchestration",
      "Priority routing",
    ],
    cta: "Coming soon",
    href: "#pricing",
    external: false,
    featured: false,
    comingSoon: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    detail: "Security, scale, and support for teams shipping with Cognilance.",
    points: [
      "Custom token limits",
      "Dedicated support",
      "Team workspaces",
      "SLA and security review",
    ],
    cta: "Coming soon",
    href: "#pricing",
    external: false,
    featured: false,
    comingSoon: true,
  },
];

export function Pricing() {
  return (
    <section className="section" id="pricing">
      <div className="container">
        <Reveal>
          <p className="eyebrow">Pricing</p>
          <h2>Simple plans. Start free.</h2>
          <p className="lead">
            Start on Free. Pro, Expert, and Enterprise are coming soon. Join
            the waitlist for early access.
          </p>
        </Reveal>
        <div className={styles.grid}>
          {tiers.map((tier, i) => (
            <Reveal key={tier.name} delayMs={i * 80}>
              <article
                className={`${styles.card} ${tier.featured ? styles.featured : ""}`}
              >
                <div className={styles.cardTop}>
                  <p className={styles.name}>{tier.name}</p>
                  {tier.comingSoon ? (
                    <span className={styles.soon}>Coming soon</span>
                  ) : null}
                </div>
                <p className={styles.price}>{tier.price}</p>
                <p className={styles.detail}>{tier.detail}</p>
                <ul className={styles.points}>
                  {tier.points.map((point) => (
                    <li key={point}>{point}</li>
                  ))}
                </ul>
                {tier.comingSoon ? (
                  <span className={`btn btnGhost ${styles.disabledCta}`}>
                    {tier.cta}
                  </span>
                ) : (
                  <a
                    href={tier.href}
                    className={`btn ${tier.featured ? "btnPrimary" : "btnGhost"}`}
                    {...(tier.external
                      ? { target: "_blank", rel: "noreferrer" }
                      : {})}
                  >
                    {tier.cta}
                  </a>
                )}
              </article>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
