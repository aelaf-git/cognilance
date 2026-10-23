import type { ReactNode } from "react";
import ClickSpark from "./ClickSpark";
import { Footer } from "./Footer";
import { SiteHeader } from "./SiteHeader";
import styles from "./LegalPage.module.css";

export function LegalPage({
  eyebrow,
  title,
  lead,
  children,
}: {
  eyebrow: string;
  title: string;
  lead: string;
  children: ReactNode;
}) {
  return (
    <ClickSpark
      sparkColor="#ffffff"
      sparkSize={10}
      sparkRadius={15}
      sparkCount={8}
      duration={400}
    >
      <SiteHeader />
      <main className={styles.main}>
        <article className="container">
          <p className="eyebrow">{eyebrow}</p>
          <h1>{title}</h1>
          <p className="lead">{lead}</p>
          <div className={styles.body}>{children}</div>
        </article>
      </main>
      <Footer />
    </ClickSpark>
  );
}
