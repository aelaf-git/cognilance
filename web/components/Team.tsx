import Image from "next/image";
import { Reveal } from "./Reveal";
import { WAITLIST } from "@/lib/site";
import { Button } from "./Button";
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

const checks = [
  "Shared with the whole team",
  "Humans stay in control",
  "Improves with your approval",
];

export function Team() {
  return (
    <section className="section" id="founders">
      <div className="container">
        <div className={styles.split}>
          <Reveal>
            <figure className={styles.photo}>
              <Image
                src="/generated/team-band.jpg"
                alt="Engineers collaborating around a table"
                width={1280}
                height={900}
              />
            </figure>
          </Reveal>
          <Reveal delayMs={90}>
            <div className={styles.copy}>
              <h2>Built by engineers who&apos;ve lived team chaos</h2>
              <p className="lead">
                A small team shipping a shared colleague for groups, not another
                private chatbot.
              </p>
              <div className={styles.avatars} aria-label="Founders">
                {people.map((person, i) => (
                  <Image
                    key={person.name}
                    src={person.image}
                    alt={person.name}
                    width={48}
                    height={48}
                    style={{ zIndex: people.length - i }}
                  />
                ))}
                <div className={styles.count}>
                  <strong>4</strong>
                  <span>founders on the team</span>
                </div>
              </div>
              <ul className={styles.checks}>
                {checks.map((check) => (
                  <li key={check}>
                    <span aria-hidden="true">→</span>
                    {check}
                  </li>
                ))}
              </ul>
              <Button href={WAITLIST} className={styles.cta}>
                Join the waitlist
              </Button>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
