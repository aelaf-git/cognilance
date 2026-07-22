import { Reveal } from "./Reveal";
import styles from "./Solution.module.css";

const pillars = [
  {
    name: "Persist",
    body: "Every result lands in a durable registry — memory, audit trail, and continuity across sessions.",
  },
  {
    name: "Verify",
    body: "An independent validation stage catches confident errors before results reach the user.",
  },
  {
    name: "Route",
    body: "The orchestrator hires the right specialist instead of forcing one generalist to do everything.",
  },
];

export function Solution() {
  return (
    <section className="section sectionAlt" id="product">
      <div className="container">
        <div className={styles.split}>
          <Reveal>
            <p className="eyebrow">The solution</p>
            <h2>Verified, persistent, unsupervised</h2>
            <p className="lead">
              Cognilance orchestrates a marketplace of specialized AI agents —
              routing each task to the right expert, validating output, and
              settling payment when the work is done.
            </p>
          </Reveal>
          <div className={styles.pillars}>
            {pillars.map((p, i) => (
              <Reveal key={p.name} delayMs={i * 100}>
                <div className={styles.pillar}>
                  <span className={styles.index}>0{i + 1}</span>
                  <div>
                    <h3>{p.name}</h3>
                    <p>{p.body}</p>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
