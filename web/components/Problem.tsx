import { Reveal } from "./Reveal";
import styles from "./Problem.module.css";

const problems = [
  {
    title: "Hallucination",
    body: "A single generalist agent makes confident errors on complex tasks with no one to catch them before they cause damage.",
  },
  {
    title: "Stalls on complexity",
    body: "Multi-step work exposes the limits of one-size-fits-all models. They get stuck, loop, or give up entirely.",
  },
  {
    title: "Zero persistence",
    body: "When the session ends, everything is forgotten. No memory, no audit trail, no way to pick up where it left off.",
  },
];

export function Problem() {
  return (
    <section className="section" id="problem">
      <div className="container">
        <Reveal>
          <p className="eyebrow">The problem</p>
          <h2>AI agents can&apos;t be trusted to run alone</h2>
          <p className="lead">
            Most teams still babysit autonomous systems because a lone agent cannot
            verify, specialize, or remember.
          </p>
        </Reveal>
        <div className={styles.grid}>
          {problems.map((item, i) => (
            <Reveal key={item.title} delayMs={i * 90}>
              <article className={styles.item}>
                <h3>{item.title}</h3>
                <p>{item.body}</p>
              </article>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
