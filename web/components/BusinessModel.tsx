import { Reveal } from "./Reveal";
import styles from "./BusinessModel.module.css";

const audiences = [
  {
    name: "For Agencies & Freelancers",
    items: [
      "Automate client onboarding: welcome emails, folder setup, kickoff scheduling",
      "Generate and send status reports without manually checking every tool",
      "Chase unpaid invoices automatically, without the awkward follow-up",
      "Keep Slack, Gmail, Notion, and your calendar in sync without touching any of them yourself",
    ],
  },
  {
    name: "For Students & Everyday Users",
    items: [
      "Research a topic across multiple sources and get a single summarized answer",
      "Organize notes, schedules, and to-dos automatically",
      "Automate repetitive study or personal admin tasks",
    ],
  },
  {
    name: "For Developers: Using Cognilance",
    note: "No SDK required",
    items: [
      "Use existing agents to build and ship websites faster",
      "Automate parts of your own dev workflow: testing, deployment checks, documentation",
      "Chain multiple pre-built agents together for personal or client projects, without writing an agent yourself",
    ],
  },
  {
    name: "For Developers: Building on Cognilance",
    note: "With the SDK",
    items: [
      "Build your own custom agents instead of building an entire automation system from scratch",
      "Publish agents to the Cognilance marketplace and earn revenue every time they're used",
      "Extend Cognilance itself: plug your agent into the same orchestration layer everyone else builds on",
    ],
  },
];

export function BusinessModel() {
  return (
    <section className="section sectionAlt" id="use-cases">
      <div className="container">
        <Reveal>
          <p className="eyebrow">Use cases</p>
          <h2>Built for anyone with work to hand off.</h2>
          <p className="lead">
            Whether you&apos;re running a business or building the next big
            agent, Cognilance has a place for you.
          </p>
        </Reveal>
        <div className={styles.grid}>
          {audiences.map((audience, i) => (
            <Reveal key={audience.name} delayMs={i * 70}>
              <article className={styles.group}>
                <h3>{audience.name}</h3>
                {audience.note ? (
                  <p className={styles.note}>{audience.note}</p>
                ) : null}
                <ul className={styles.list}>
                  {audience.items.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </article>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
