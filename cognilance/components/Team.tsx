import Image from "next/image";
import { Reveal } from "./Reveal";
import styles from "./Team.module.css";

const people = [
  {
    name: "Aelaf Eskindir",
    role: "Founder & CEO",
    image: "/founders/aelaf.jpg",
  },
  {
    name: "Kaleb Asratemedhin",
    role: "AI Engineer",
    image: "/founders/kaleb.png",
  },
  {
    name: "Yohannes Alemayehu",
    role: "Full Stack Engineer",
    image: "/founders/yohannes.jpg",
  },
  {
    name: "Aregawi Fikre",
    role: "Full Stack Engineer",
    image: "/founders/aregawi.jpeg",
  },
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
                <Image
                  src={person.image}
                  alt={person.name}
                  width={96}
                  height={96}
                  className={styles.photo}
                />
                <div className={styles.meta}>
                  <span className={styles.name}>{person.name}</span>
                  <span className={styles.role}>{person.role}</span>
                </div>
              </li>
            </Reveal>
          ))}
        </ul>
      </div>
    </section>
  );
}
