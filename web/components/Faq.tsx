import { Reveal } from "./Reveal";
import styles from "./Faq.module.css";

const items = [
  {
    q: "Does Cognilance act without asking?",
    a: "No. Consequential actions (sending mail, changing records, applying new routines) wait for human approval.",
  },
  {
    q: "Is this a private chat for one person?",
    a: "The assistant is shared. The whole team prompts the same agents and sees the same context.",
  },
  {
    q: "Which tools does it connect to?",
    a: "Slack, Gmail, Google Drive, Calendar, Docs, Sheets, Notion, and more to come. You connect what the team already uses.",
  },
  {
    q: "When can we start?",
    a: "Access opens in waves. Join the waitlist and we will invite teams ready to work with shared agents.",
  },
];

export function Faq() {
  return (
    <section className="section" id="faq">
      <div className="container">
        <Reveal>
          <div className={styles.header}>
            <p className="eyebrow">FAQ</p>
            <h2>Frequently asked questions</h2>
            <p className="lead">
              The key points about approvals, shared context, tools, and access
              before you join.
            </p>
          </div>
        </Reveal>
        <div className={styles.list}>
          {items.map((item, i) => (
            <details key={item.q} className={styles.item} open={i === 0}>
              <summary>
                <h3>{item.q}</h3>
                <span aria-hidden="true">+</span>
              </summary>
              <p>{item.a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
