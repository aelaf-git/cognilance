import type { Metadata } from "next";
import ClickSpark from "@/components/ClickSpark";
import { Footer } from "@/components/Footer";
import { SiteHeader } from "@/components/SiteHeader";
import styles from "./developers.module.css";

export const metadata: Metadata = {
  title: "Developers | Cognilance AI",
  description: "Developer docs and tools for Cognilance. Under construction.",
};

export default function DevelopersPage() {
  return (
    <ClickSpark
      sparkColor="#ff492c"
      sparkSize={10}
      sparkRadius={15}
      sparkCount={8}
      duration={400}
    >
      <SiteHeader />
      <main className={styles.main}>
        <section className={styles.hero}>
          <div className={`container ${styles.inner}`}>
            <p className={styles.badge}>
              <svg
                className={styles.badgeIcon}
                viewBox="0 0 24 24"
                fill="none"
                aria-hidden="true"
              >
                <path
                  d="M12 2.5 3.5 20.5h17L12 2.5Z"
                  stroke="currentColor"
                  strokeWidth="1.75"
                  strokeLinejoin="round"
                />
                <path
                  d="M8.2 14h7.6M6.6 17.5h10.8"
                  stroke="currentColor"
                  strokeWidth="1.75"
                  strokeLinecap="round"
                />
              </svg>
              Under construction
            </p>
            <h1 className={styles.title}>Developers</h1>
            <p className={styles.lead}>
              Docs, SDK guides, and agent publishing tools are on the way. Check
              back soon.
            </p>
            <div className={styles.actions}>
              <a href="/" className="btn btnGhost">
                Back to home
              </a>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </ClickSpark>
  );
}
