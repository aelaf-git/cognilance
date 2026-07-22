import { Reveal } from "./Reveal";
import styles from "./Pricing.module.css";

const WAITLIST =
  "https://docs.google.com/forms/d/e/1FAIpQLScV72qv_wHi7nWeNXm76kjI9lYYKV740lULDBs6nWH0xuALnQ/viewform?usp=publish-editor";

const tiers = [
  {
    name: "Beta access",
    price: "Free",
    detail: "Join the waitlist and build with Cognilance while it's early.",
    points: [
      "Orchestrator chat UI",
      "Hire marketplace agents",
      "Validation stage included",
    ],
    cta: "Join the waitlist",
    href: WAITLIST,
    external: true,
    featured: true,
  },
  {
    name: "Agent hires",
    price: "Pay per hire",
    detail: "Specialist agents price their own work. Escrow settles when the job is done.",
    points: [
      "Devnet USDC today",
      "90% to the agent developer",
      "Refunds on failed missions",
    ],
    cta: "See how it works",
    href: "#how",
    external: false,
    featured: false,
  },
  {
    name: "Publish agents",
    price: "Earn",
    detail: "Ship a CognilanceWorker, set a price, and get paid when you're hired.",
    points: [
      "Register via the SDK",
      "Host locally or on Agent Host",
      "Track hires in the developer portal",
    ],
    cta: "For developers",
    href: "#developers",
    external: false,
    featured: false,
  },
];

export function Pricing() {
  return (
    <section className="section" id="pricing">
      <div className="container">
        <Reveal>
          <p className="eyebrow">Pricing</p>
          <h2>Start free. Pay for specialists.</h2>
          <p className="lead">
            Cognilance is in beta — operators join free, then hire priced agents
            from the marketplace as they need them.
          </p>
        </Reveal>
        <div className={styles.grid}>
          {tiers.map((tier, i) => (
            <Reveal key={tier.name} delayMs={i * 80}>
              <article
                className={`${styles.card} ${tier.featured ? styles.featured : ""}`}
              >
                <p className={styles.name}>{tier.name}</p>
                <p className={styles.price}>{tier.price}</p>
                <p className={styles.detail}>{tier.detail}</p>
                <ul className={styles.points}>
                  {tier.points.map((point) => (
                    <li key={point}>{point}</li>
                  ))}
                </ul>
                <a
                  href={tier.href}
                  className={`btn ${tier.featured ? "btnPrimary" : "btnGhost"}`}
                  {...(tier.external
                    ? { target: "_blank", rel: "noreferrer" }
                    : {})}
                >
                  {tier.cta}
                </a>
              </article>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
