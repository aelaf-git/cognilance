import Image from "next/image";
import { Reveal } from "./Reveal";
import styles from "./Integrations.module.css";

const integrations = [
  { name: "Slack", src: "/integrations/slack.webp" },
  { name: "Gmail", src: "/integrations/gmail.webp" },
  { name: "Google Drive", src: "/integrations/drive.webp" },
  { name: "Calendar", src: "/integrations/calendar.webp" },
  { name: "Docs", src: "/integrations/docs.png" },
  { name: "Sheets", src: "/integrations/sheets.png" },
  { name: "Notion", src: "/integrations/notion.png" },
  { name: "GitHub", src: "/integrations/github.webp" },
];

function LogoTrack({ ariaHidden = false }: { ariaHidden?: boolean }) {
  return (
    <ul className={styles.track} aria-hidden={ariaHidden || undefined}>
      {integrations.map((item) => (
        <li key={item.name} className={styles.item}>
          <Image
            src={item.src}
            alt=""
            width={36}
            height={36}
            className={styles.icon}
          />
          <span>{item.name}</span>
        </li>
      ))}
    </ul>
  );
}

export function Integrations() {
  return (
    <section className={`section ${styles.wrap}`} id="integrations">
      <div className="container">
        <Reveal>
          <header className={styles.header}>
            <p className="eyebrow">Integrations</p>
            <h2>Connects to the tools you already use</h2>
            <p className={`lead ${styles.lead}`}>
              Slack, Gmail, Drive, Calendar, Docs, Sheets, Notion, GitHub, and
              more to come.
            </p>
          </header>
        </Reveal>
      </div>

      <div className={styles.marquee} aria-label="Supported integrations">
        <div className={styles.viewport}>
          <div className={styles.rail}>
            <LogoTrack />
            <LogoTrack ariaHidden />
            <LogoTrack ariaHidden />
            <LogoTrack ariaHidden />
          </div>
        </div>
      </div>
    </section>
  );
}
