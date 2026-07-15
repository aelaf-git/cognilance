import { Reveal } from "./Reveal";
import styles from "./Waitlist.module.css";

const WAITLIST_URL =
  "https://docs.google.com/forms/d/e/1FAIpQLScV72qv_wHi7nWeNXm76kjI9lYYKV740lULDBs6nWH0xuALnQ/viewform?usp=publish-editor";

export function Waitlist() {
  return (
    <section className={`section ${styles.wrap}`} id="waitlist">
      <div className="container">
        <Reveal>
          <p className="eyebrow">Beta access</p>
          <h2>Build with Cognilance while it&apos;s early</h2>
          <p className="lead">
            We&apos;re onboarding teams who need production-grade multi-agent
            orchestration — not another demo sandbox. Join the beta waitlist.
          </p>
        </Reveal>
        <Reveal delayMs={120}>
          <div className={styles.ctaBlock}>
            <a
              href={WAITLIST_URL}
              className="btn btnPrimary"
              target="_blank"
              rel="noreferrer"
            >
              Join the waitlist
            </a>
            <p className={styles.hint}>
              Limited beta · No spam · Product updates only
            </p>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
