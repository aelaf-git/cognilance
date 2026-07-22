import { Reveal } from "./Reveal";
import styles from "./Team.module.css";

const people = [
  { name: "Aelaf Eskindir", role: "Founder & CEO" },
  { name: "Kaleb Asratemedhin", role: "AI Engineer" },
  { name: "Yohannes Alemayehu", role: "Full Stack Engineer" },
  { name: "Aregawi Fikre", role: "Full Stack Engineer" },
];

export function Team() {
  return (
    <section className="section sectionAlt" id="founders">
      <div className="container">
        <Reveal>
          <p className="eyebrow">Founders</p>
          <h2>Built by engineers who&apos;ve lived the problem</h2>
        </Reveal>
        <ul className={styles.list}>
          {people.map((person, i) => (
            <Reveal key={person.name} delayMs={i * 80}>
              <li className={styles.person}>
                <span className={styles.name}>{person.name}</span>
                <span className={styles.role}>{person.role}</span>
              </li>
            </Reveal>
          ))}
        </ul>
      </div>
    </section>
  );
}
