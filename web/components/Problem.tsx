import { Reveal } from "./Reveal";
import styles from "./Problem.module.css";

const problems = [
  {
    title: "Repetitive tasks eat billable hours",
    body: "Onboarding, status updates, and admin work pile up, necessary, but never the reason you started the business.",
  },
  {
    title: "Your tools don't talk to each other",
    body: "Slack, Gmail, Notion, and your calendar all live in separate worlds. Someone has to be the glue, every time.",
  },
  {
    title: "Hiring help doesn't scale",
    body: "A VA or extra hire costs more, takes time to train, and still needs managing. The problem outgrows the fix.",
  },
];

export function Problem() {
  return (
    <section className="section" id="problem">
      <div className="container">
        <Reveal>
          <p className="eyebrow">The problem</p>
          <h2>
            Agencies and freelancers lose hours every week to tasks that have
            nothing to do with the work they&apos;re actually hired for.
          </h2>
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
