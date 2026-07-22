import { Reveal } from "./Reveal";
import { OrchestrationDiagram } from "./OrchestrationDiagram";
import styles from "./Solution.module.css";

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
                A network of AI agents that handles the repetitive, cross-tool
                tasks running your client work — automatically, and without you
                managing a single one of them.
              </p>
              <p className={styles.body}>
                Cognilance connects to the tools you already use — Gmail, Slack,
                Notion, your calendar — and coordinates AI agents to carry out the
                tasks in between: sending the welcome email, updating the tracker,
                chasing the invoice. You describe what needs to happen once;
                Cognilance handles it every time after that, quietly, in the
                background, so it never becomes your job again.
              </p>
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
