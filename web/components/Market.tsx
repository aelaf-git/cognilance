import { Reveal } from "./Reveal";
import styles from "./Market.module.css";

const metrics = [
  { value: "$10.9B", label: "2026 market size", detail: "Current AI agent market valuation" },
  { value: "$182.9B", label: "2033 market size", detail: "Projected value in seven years" },
  { value: "49.6%", label: "CAGR", detail: "Compound annual growth through 2033" },
  { value: "89%", label: "Pilots that fail", detail: "Never reach production due to trust gaps" },
];

export function Market() {
  return (
    <section className={`section ${styles.wrap}`}>
      <div className="container">
        <Reveal>
          <p className="eyebrow">Market opportunity</p>
          <h2>A $182B market — and most pilots still fail</h2>
        </Reveal>
        <div className={styles.grid}>
          {metrics.map((m, i) => (
            <Reveal key={m.label} delayMs={i * 100} className={styles.metric}>
              <p className={styles.value}>{m.value}</p>
              <p className={styles.label}>{m.label}</p>
              <p className={styles.detail}>{m.detail}</p>
            </Reveal>
          ))}
        </div>
        <Reveal>
          <p className={styles.source}>
            Sources: Grand View Research &amp; Gartner, 2026
          </p>
        </Reveal>
      </div>
    </section>
  );
}
