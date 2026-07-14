import { Reveal } from "./Reveal";
import styles from "./Proof.module.css";

export function Proof() {
  return (
    <section className={`section ${styles.wrap}`}>
      <div className="container">
        <Reveal>
          <p className="eyebrow">Proof of the problem</p>
          <p className={styles.stat}>89%</p>
          <h2 className={styles.title}>
            of AI agent pilots never reach production
          </h2>
          <p className={styles.body}>
            Not because the underlying models are bad — but because organizations
            cannot trust autonomous agents to operate without constant human
            oversight.
          </p>
          <p className={styles.source}>Source: Gartner, 2026</p>
        </Reveal>
      </div>
    </section>
  );
}
