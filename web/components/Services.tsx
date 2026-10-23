import { Reveal } from "./Reveal";
import styles from "./Services.module.css";

const items = [
  {
    number: "01.",
    title: "Connect your tools",
    body: "Chat, email, docs, trackers: where work already lives. The assistant reads, drafts, updates, and schedules there.",
  },
  {
    number: "02.",
    title: "Share one conversation",
    body: "The whole team prompts the same agents together. One thread, shared context, no private silos.",
  },
  {
    number: "03.",
    title: "Specialists coordinate",
    body: "Research, writing, email, monitoring: divided and combined, then brought back as one answer.",
  },
  {
    number: "04.",
    title: "Improve with approval",
    body: "Better routines are proposed; you decide what applies. Humans stay in control of consequential actions.",
  },
];

export function Services() {
  return (
    <section className="section sectionLight" id="how">
      <div className="container">
        <div className={styles.intro}>
          <Reveal>
            <h2 id="product">Four steps. One shared assistant.</h2>
          </Reveal>
          <Reveal delayMs={80}>
            <div>
              <p className="lead">
                Not a private chat for one person: agents the group works with
                together, that learn with your approval.
              </p>
            </div>
          </Reveal>
        </div>

        <div className={styles.grid}>
          {items.map((item, i) => (
            <Reveal key={item.title} delayMs={i * 70}>
              <article className={`ui-card-interactive ${styles.card}`}>
                <div className={styles.body}>
                  <div className={styles.titleLine}>
                    <span className={styles.number}>{item.number}</span>
                    <h3>{item.title}</h3>
                  </div>
                  <p>{item.body}</p>
                </div>
                <span className={styles.arrow} aria-hidden="true">
                  ↗
                </span>
              </article>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
