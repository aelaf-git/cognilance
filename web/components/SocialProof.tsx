import Image from "next/image";
import { Reveal } from "./Reveal";
import styles from "./SocialProof.module.css";

const integrations = [
  { name: "Slack", src: "/integrations/slack.webp" },
  { name: "Google Drive", src: "/integrations/drive.webp" },
  { name: "Google Calendar", src: "/integrations/calendar.webp" },
  { name: "Gmail", src: "/integrations/gmail.webp" },
  { name: "Notion", src: "/integrations/notion.png" },
  { name: "Google Docs", src: "/integrations/docs.png" },
  { name: "Google Sheets", src: "/integrations/sheets.png" },
];

export function SocialProof() {
  return (
    <section className={`section ${styles.wrap}`} id="social-proof">
      <div className="container">
        <Reveal>
          <p className="eyebrow">Social Proof</p>
          <h2>Trusted by builders. Connected to your stack.</h2>
        </Reveal>

        <div className={styles.blocks}>
          <Reveal delayMs={80}>
            <div className={styles.block}>
              <p className={styles.blockLabel}>Backers</p>
              <p className={styles.blockLead}>We are backed by Dev3pack.</p>
              <a
                href="https://dev3pack.com"
                className={styles.backer}
                target="_blank"
                rel="noreferrer"
              >
                <Image
                  src="/partners/dev3pack.png"
                  alt="Dev3pack"
                  width={120}
                  height={158}
                  className={styles.backerLogo}
                />
                <span className={styles.backerName}>Dev3pack</span>
              </a>
            </div>
          </Reveal>

          <Reveal delayMs={140}>
            <div className={styles.block}>
              <p className={styles.blockLabel}>Integrations</p>
              <p className={styles.blockLead}>
                Slack, Google Drive, Google Calendar, Gmail, Notion, Google
                Docs, Google Sheets and many more to come.
              </p>
              <ul className={styles.logoGrid}>
                {integrations.map((item) => (
                  <li key={item.name} className={styles.logoItem}>
                    <Image
                      src={item.src}
                      alt={item.name}
                      width={40}
                      height={40}
                      className={styles.logo}
                    />
                    <span>{item.name}</span>
                  </li>
                ))}
                <li className={`${styles.logoItem} ${styles.more}`}>
                  <span className={styles.moreMark}>+</span>
                  <span>Many more to come</span>
                </li>
              </ul>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
