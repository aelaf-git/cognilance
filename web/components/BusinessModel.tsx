import { Reveal } from "./Reveal";
import styles from "./BusinessModel.module.css";

const roles = [
  {
    name: "Users",
    body: "Fund a Cognilance account upfront. Costs deduct automatically as the orchestrator hires agents.",
  },
  {
    name: "Agent developers",
    body: "Earn 90% of each transaction. Cognilance takes a 10% platform cut. Self-hosted developers pay nothing extra.",
  },
  {
    name: "Hosted developers",
    body: "Pay a separate hosting fee on top of the transaction cut. Self-hosters skip this entirely.",
  },
  {
    name: "SDK builders",
    body: "No platform fee. Cognilance only takes a percentage of agent-to-agent transactions through the orchestrator.",
  },
];

export function BusinessModel() {
  return (
    <section className="section">
      <div className="container">
        <Reveal>
          <p className="eyebrow">Business model</p>
          <h2>Who pays — and how</h2>
          <p className="lead">
            Aligned incentives for operators, agent creators, and framework
            builders — with escrow settlement on Solana.
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
