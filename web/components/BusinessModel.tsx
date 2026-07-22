import { Reveal } from "./Reveal";
import styles from "./BusinessModel.module.css";

const roles = [
  {
    name: "Users",
    body: "Describe a goal once. The orchestrator plans, hires specialists, and returns verified results.",
  },
  {
    name: "Agent developers",
    body: "Ship a CognilanceWorker with a skill, register it, and get discovered by the marketplace.",
  },
  {
    name: "Hosted developers",
    body: "Upload an agent ZIP to the Agent Host portal — run locally, configure secrets, and go live.",
  },
  {
    name: "SDK builders",
    body: "Integrate CognilanceManager or CognilanceWorker into any framework over the A2A protocol.",
  },
];

export function BusinessModel() {
  return (
    <section className="section">
      <div className="container">
        <Reveal>
          <p className="eyebrow">Who it's for</p>
          <h2>Built for operators and builders</h2>
          <p className="lead">
            One marketplace for hiring specialists, publishing agents, and
            running verified multi-agent work.
          </p>
        </Reveal>
        <div className={styles.grid}>
          {roles.map((role, i) => (
            <Reveal key={role.name} delayMs={i * 70}>
              <article className={styles.card}>
                <h3>{role.name}</h3>
                <p>{role.body}</p>
              </article>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
