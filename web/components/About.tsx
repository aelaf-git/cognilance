import { Reveal } from "./Reveal";
import styles from "./About.module.css";

const pillars = [
  {
    title: "Group conversation",
    body: "Several people share one conversation with the same agents. Context, instructions, and results belong to the group.",
  },
  {
    title: "Improvement with approval",
    body: "A learning layer gathers signals from the team’s tools and feedback, then proposes better routines. Changes apply only with human approval.",
  },
  {
    title: "Proactive alerts",
    body: "Because it sees across sources, it can notice risks, contradictions, and idle work that a person in one tool would miss.",
  },
  {
    title: "Open SDK",
    body: "Use Cognilance’s agents and learning layer inside your own AI workflows, or call them as building blocks.",
  },
];

export function About() {
  return (
    <section className={`section ${styles.wrap}`} id="about">
      <div className="container">
        <Reveal>
          <header className={styles.header}>
            <p className="eyebrow">Company</p>
            <h2>About</h2>
          </header>
        </Reveal>

        <Reveal delayMs={80}>
          <p className={`lead ${styles.lead}`}>
            Cognilance is an AI team assistant built around groups: a startup, a
            department, an NGO, or a study class. Several people work with the
            same agents in the same conversation. It serves a single person well
            too. Teams are the primary focus.
          </p>
        </Reveal>

        <ul className={styles.pillars}>
          {pillars.map((pillar, i) => (
            <Reveal key={pillar.title} delayMs={140 + i * 50} as="li">
              <div className={styles.pillar}>
                <h3>{pillar.title}</h3>
                <p>{pillar.body}</p>
              </div>
            </Reveal>
          ))}
        </ul>
      </div>
    </section>
  );
}
