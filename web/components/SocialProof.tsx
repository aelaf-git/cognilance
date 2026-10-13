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

type Backer = {
  name: string;
  shortName?: string;
  src: string;
  href?: string;
  width: number;
  height: number;
};

const backers: Backer[] = [
  {
    name: "Dev3pack",
    src: "/partners/dev3pack.png",
    href: "https://dev3pack.com",
    width: 120,
    height: 158,
  },
  {
    name: "Ethiopian Artificial Intelligence Institute",
    shortName: "AI Institute",
    src: "/partners/ai-institute.png",
    width: 160,
    height: 160,
  },
];

function BackerCard({ name, shortName, src, href, width, height }: Backer) {
  const content = (
    <>
      <Image
        src={src}
        alt={name}
        width={width}
        height={height}
        className={styles.backerLogo}
      />
      <span className={styles.backerName}>{shortName ?? name}</span>
    </>
  );

  if (href) {
    return (
      <a
        href={href}
        className={styles.backer}
        target="_blank"
        rel="noreferrer"
      >
        {content}
      </a>
    );
  }

  return <div className={styles.backer}>{content}</div>;
}

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
              <p className={styles.blockLead}>
                Backed by Dev3pack and the Ethiopian Artificial Intelligence
                Institute.
              </p>
              <ul className={styles.backerRow}>
                {backers.map((backer) => (
                  <li key={backer.name}>
                    <BackerCard {...backer} />
                  </li>
                ))}
              </ul>
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
