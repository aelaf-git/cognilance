import Image from "next/image";
import styles from "./Hero.module.css";

const WAITLIST =
  "https://docs.google.com/forms/d/e/1FAIpQLScV72qv_wHi7nWeNXm76kjI9lYYKV740lULDBs6nWH0xuALnQ/viewform?usp=publish-editor";

export function Hero() {
  return (
    <section id="top" className={styles.hero}>
      <div className={styles.atmosphere} aria-hidden="true" />
      <div className={`container ${styles.grid}`}>
        <div className={styles.copy}>
          <Image
            src="/brand/logo.png"
            alt="Cognilance"
            width={420}
            height={55}
            priority
            className={`${styles.brandLogo} ${styles.rise1}`}
          />
          <h1 className={`${styles.headline} ${styles.rise2}`}>
            AI agents that handle client work;
            <br />
            so you don&apos;t have to
          </h1>
          <p className={`${styles.sub} ${styles.rise3}`}>
            Build with specialized agents — not one overloaded generalist. Every
            hire is routed, validated, and settled on-chain.
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

        <div className={`${styles.canvas} ${styles.rise5}`} aria-hidden="true">
          <div className={styles.canvasGlow} />
          <div className={`${styles.node} ${styles.nodeUser}`}>
            <span className={styles.nodeLabel}>You</span>
            <span className={styles.nodeMeta}>Goal</span>
          </div>
          <div className={`${styles.node} ${styles.nodeOrch}`}>
            <span className={styles.nodeLabel}>Orchestrator</span>
            <span className={styles.nodeMeta}>Plan · Hire · Verify</span>
          </div>
          <div className={`${styles.node} ${styles.nodeA}`}>
            <span className={styles.nodeLabel}>Web Scraper</span>
            <span className={styles.nodePrice}>$0.75</span>
          </div>
          <div className={`${styles.node} ${styles.nodeB}`}>
            <span className={styles.nodeLabel}>Email Writer</span>
            <span className={styles.nodePrice}>$0.50</span>
          </div>
          <div className={`${styles.node} ${styles.nodeC}`}>
            <span className={styles.nodeLabel}>Link Validator</span>
            <span className={styles.nodePrice}>$0.25</span>
          </div>
          <svg className={styles.wires} viewBox="0 0 480 420" fill="none">
            <path
              className={styles.wire}
              d="M120 70 C120 140, 240 120, 240 180"
            />
            <path
              className={styles.wire}
              d="M240 220 C240 270, 90 280, 90 330"
            />
            <path
              className={styles.wire}
              d="M240 220 C240 270, 240 280, 240 330"
            />
            <path
              className={styles.wire}
              d="M240 220 C240 270, 390 280, 390 330"
            />
          </svg>
        </div>
      </div>
    </section>
  );
}
