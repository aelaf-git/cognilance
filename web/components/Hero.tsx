import styles from "./Hero.module.css";

export function Hero() {
  return (
    <section id="top" className={styles.hero}>
      <div className={styles.atmosphere} aria-hidden="true" />
      <div className={`container ${styles.content}`}>
        <p className={`${styles.chip} ${styles.rise1}`}>
          <span className="betaChip">Beta</span>
          <span className={styles.tagline}>Marketplace of Minds</span>
        </p>
        <p className={`${styles.brand} ${styles.rise2}`}>Cognilance</p>
        <h1 className={`${styles.headline} ${styles.rise3}`}>
          One AI agent hallucinates.
          <br />
          A thousand, verified, don&apos;t.
        </h1>
        <p className={`${styles.sub} ${styles.rise4}`}>
          Trustworthy autonomous AI built for production, not demos.
        </p>
        <div className={`${styles.actions} ${styles.rise5}`}>
          <a href="#waitlist" className="btn btnPrimary">
            Join the beta
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
    </section>
  );
}
