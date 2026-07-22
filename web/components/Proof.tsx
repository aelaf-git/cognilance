import { Reveal } from "./Reveal";
import styles from "./Proof.module.css";

const stats = [
  { value: "89%", label: "of AI agent pilots never reach production" },
  { value: "$182B", label: "projected AI agent market by 2033" },
  { value: "3+", label: "specialist agents online in the marketplace beta" },
];

export function Proof() {
  return (
    <section className={styles.wrap}>
      <div className={`container ${styles.inner}`}>
        {stats.map((stat, i) => (
          <Reveal key={stat.label} delayMs={i * 80}>
            <div className={styles.stat}>
              <p className={styles.value}>{stat.value}</p>
              <p className={styles.label}>{stat.label}</p>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
