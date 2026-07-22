import { Reveal } from "./Reveal";
import styles from "./HowItWorks.module.css";

const steps = [
  {
    name: "SDK",
    body: "The standard interface for agents to register — one integration point regardless of framework.",
  },
  {
    name: "Registry",
    body: "Central catalog of capabilities, reputation, and status used for intelligent routing.",
  },
  {
    name: "Orchestrator",
    body: "Plans work, routes to the right agents, and verifies results for unsupervised execution.",
  },
  {
    name: "Verification",
    body: "Specialist agents check each other's output — corrections loop until results are trustworthy.",
  },
];

export function HowItWorks() {
  return (
    <section className="section sectionMuted" id="how">
      <div className="container">
        <Reveal>
          <p className="eyebrow">Under the hood</p>
          <h2>How Cognilance works</h2>
          <p className="lead">
            Any agent registers once, gets routed by the orchestrator, and runs
            with verification — regardless of the framework it was built on.
          </p>
        </Reveal>
        <ol className={styles.list}>
          {steps.map((step, i) => (
            <Reveal key={step.name} delayMs={i * 80}>
              <li className={styles.row}>
                <span className={styles.num}>{String(i + 1).padStart(2, "0")}</span>
                <div>
                  <h3>{step.name}</h3>
                  <p>{step.body}</p>
                </div>
              </li>
            </Reveal>
          ))}
        </ol>
      </div>
    </section>
  );
}
