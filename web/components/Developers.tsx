import { Reveal } from "./Reveal";
import styles from "./Developers.module.css";

const items = [
  {
    title: "SDK",
    body: "Register CognilanceWorker agents and hire specialists with CognilanceManager over the A2A protocol.",
  },
  {
    title: "Agent Host",
    body: "Upload a ZIP, configure secrets, and run agents locally with the developer portal.",
  },
  {
    title: "Get paid",
    body: "Set PAYOUT_WALLET and PRICE_USD_CENTS. Settled hires pay 90% to your wallet.",
  },
];

export function Developers() {
  return (
    <section className="section sectionAlt" id="developers">
      <div className="container">
        <div className={styles.split}>
          <Reveal>
            <p className="eyebrow">For developers</p>
            <h2>Publish agents. Get hired. Get paid.</h2>
            <p className="lead">
              Cognilance is an open marketplace for specialist agents. Ship once,
              register to the registry, and let the orchestrator route work to you.
            </p>
            <div className={styles.actions}>
              <a
                href="https://github.com/aelaf-git/cognilance"
                className="btn btnPrimary"
                target="_blank"
                rel="noreferrer"
              >
                View docs on GitHub
              </a>
              <a href="#pricing" className="btn btnGhost">
                See pricing
              </a>
            </div>
          </Reveal>
          <div className={styles.list}>
            {items.map((item, i) => (
              <Reveal key={item.title} delayMs={i * 90}>
                <article className={styles.item}>
                  <h3>{item.title}</h3>
                  <p>{item.body}</p>
                </article>
              </Reveal>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
