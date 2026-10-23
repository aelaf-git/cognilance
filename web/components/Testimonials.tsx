import Image from "next/image";
import { Reveal } from "./Reveal";
import styles from "./Testimonials.module.css";

const items = [
  {
    quote:
      "Placeholder: our Friday update used to take half a day. Now the draft is waiting, and nothing sends until we approve it.",
    author: "Maya Bekele",
    initials: "MB",
    role: "Ops lead, early-stage startup (placeholder)",
    avatar: "/generated/avatar-01.jpg",
  },
  {
    quote:
      "Placeholder: the study group finally has one shared notebook and reminders when a topic sits idle.",
    author: "Daniel Haile",
    initials: "DH",
    role: "Graduate student (placeholder)",
    avatar: "/generated/avatar-02.jpg",
  },
  {
    quote:
      "Placeholder: donor reports used to scramble every quarter. Activity and spend now land in one draft we can check.",
    author: "Sara Mekonnen",
    initials: "SM",
    role: "Program manager, NGO (placeholder)",
    avatar: "/generated/avatar-03.jpg",
  },
];

export function Testimonials() {
  const columns = [
    items,
    [...items.slice(2), ...items.slice(0, 2)],
    [...items.slice(1), ...items.slice(0, 1)],
  ];

  return (
    <section className={`section ${styles.wrap}`} id="reviews">
      <div className="container">
        <Reveal>
          <div className={styles.header}>
            <p className="eyebrow">Placeholder reviews</p>
            <h2>What teams will say</h2>
            <p className="lead">
              Sample quotes for layout. Replace with real voices when the
              waitlist opens.
            </p>
          </div>
        </Reveal>
        <div className={styles.marquee}>
          {columns.map((column, columnIndex) => (
            <div
              key={columnIndex}
              className={`${styles.col} ${columnIndex > 0 ? styles.hideMobile : ""}`}
            >
              <div
                className={`${styles.track} ${
                  columnIndex === 1
                    ? styles.slow
                    : columnIndex === 2
                      ? styles.fast
                      : ""
                }`}
              >
                {[0, 1, 2].map((copyIndex) => (
                  <div
                    key={copyIndex}
                    className={styles.stack}
                    aria-hidden={copyIndex > 0}
                  >
                    {column.map((item) => (
                      <article key={`${copyIndex}-${item.author}`} className={styles.card}>
                        <p>{item.quote}</p>
                        <footer>
                          <span className={styles.avatar}>
                            <Image
                              src={item.avatar}
                              alt=""
                              width={40}
                              height={40}
                            />
                          </span>
                          <div>
                            <cite>{item.author}</cite>
                            <span>{item.role}</span>
                          </div>
                        </footer>
                      </article>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
