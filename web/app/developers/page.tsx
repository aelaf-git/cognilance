import type { Metadata } from "next";
import ClickSpark from "@/components/ClickSpark";
import { Button } from "@/components/Button";
import { Footer } from "@/components/Footer";
import { SiteHeader } from "@/components/SiteHeader";
import styles from "./developers.module.css";

export const metadata: Metadata = {
  title: {
    absolute: "Cognilance AI",
  },
  description: "Developer docs and tools for Cognilance. Under construction.",
};

export default function DevelopersPage() {
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
        <section className={styles.hero}>
          <div className="container">
            <p className="eyebrow">Developers & SDK</p>
            <h1>Build with the SDK</h1>
            <p className="lead">
              Docs, SDK guides, and agent publishing tools are on the way. This
              page is a placeholder until that surface ships.
            </p>
            <div className={styles.actions}>
              <Button href="/" variant="ghost">
                Back to home
              </Button>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </ClickSpark>
  );
}
