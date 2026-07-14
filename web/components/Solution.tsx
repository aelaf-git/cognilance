import { Reveal } from "./Reveal";
import styles from "./Solution.module.css";

const pillars = [
  {
    name: "Persist",
    body: "Every result lands in a durable registry — memory, audit trail, and continuity across sessions.",
  },
  {
    name: "Verify",
    body: "An independent verification layer catches confident errors before they ship to production systems.",
  },
  {
    name: "Route",
    body: "The orchestrator sends each task to the right specialist instead of forcing one generalist to do everything.",
  },
];

export function Solution() {
  return (
    <section className="section" id="product">
      <div className="container">
        <Reveal>
          <p className="eyebrow">The solution</p>
          <h2>Verified, persistent, unsupervised</h2>
          <p className="lead">
            Cognilance orchestrates a network of specialized AI agents — routing
            each task to the right expert, validating output, and persisting every
            result. A system you can trust to run unsupervised, across any
            framework.
          </p>
        </Reveal>
        <div className={styles.pillars}>
          {pillars.map((p, i) => (
            <Reveal key={p.name} delayMs={i * 100}>
              <div className={styles.pillar}>
                <span className={styles.index}>0{i + 1}</span>
                <h3>{p.name}</h3>
                <p>{p.body}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
