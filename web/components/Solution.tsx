import { Reveal } from "./Reveal";
import { OrchestrationDiagram } from "./OrchestrationDiagram";
import styles from "./Solution.module.css";

const points = [
  {
    title: "Thinks it through",
    body: "Reasons step by step instead of guessing, so it handles multi-part requests reliably.",
  },
  {
    title: "Does it all at once",
    body: "Runs several tasks in parallel instead of making you wait in line.",
  },
  {
    title: "Never clocks out",
    body: "Runs in the cloud, so work keeps going even after you've shut your laptop.",
  },
];

export function Solution() {
  return (
    <section className="section sectionAlt" id="product">
      <div className="container">
        <div className={styles.split}>
          <Reveal>
            <div className={styles.copy}>
              <p className="eyebrow">The solution</p>
              <h2>Cognilance is the team that never needs onboarding.</h2>
              <p className="lead">
                A network of AI agents that thinks through your work, handles
                several things at once, and keeps running even when you&apos;ve
                logged off.
              </p>
              <p className={styles.body}>
                Cognilance connects to the tools you already use and coordinates
                specialized AI agents to run the tasks behind your client work.
              </p>
              <ul className={styles.points}>
                {points.map((point) => (
                  <li key={point.title} className={styles.point}>
                    <strong>{point.title}</strong>
                    <span>{point.body}</span>
                  </li>
                ))}
              </ul>
            </div>
          </Reveal>

          <Reveal delayMs={120}>
            <OrchestrationDiagram />
          </Reveal>
        </div>
      </div>
    </section>
  );
}
