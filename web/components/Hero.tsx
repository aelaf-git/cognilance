import { EnergyBubble } from "@/components/EnergyBubble";
import styles from "./Hero.module.css";

const WAITLIST =
  "https://docs.google.com/forms/d/e/1FAIpQLScV72qv_wHi7nWeNXm76kjI9lYYKV740lULDBs6nWH0xuALnQ/viewform?usp=publish-editor";

export function Hero() {
  return (
    <section id="top" className={styles.hero}>
      <div className={styles.atmosphere} aria-hidden="true" />
      <div className={`container ${styles.grid}`}>
        <div className={styles.copy}>
          <h1 className={`${styles.headline} ${styles.rise2}`}>
            AI agents that handle
            <br />
            boring work.
          </h1>
          <p className={`${styles.sub} ${styles.rise3}`}>
            So you don&apos;t have to.
          </p>
          <div className={`${styles.actions} ${styles.rise4}`}>
            <a
              href={WAITLIST}
              className="btn btnPrimary"
              target="_blank"
              rel="noreferrer"
            >
              Join the waitlist
            </a>
            <a
              href="https://github.com/aelaf-git/cognilance"
              className="btn btnGhost"
              target="_blank"
              rel="noreferrer"
            >
              View docs
            </a>
          </div>
        </div>

        <div className={`${styles.visual} ${styles.rise5}`}>
          <EnergyBubble size="lg" />
        </div>
      </div>
    </section>
  );
}
