import type { Metadata } from "next";
import ClickSpark from "@/components/ClickSpark";
import { Footer } from "@/components/Footer";
import { SiteHeader } from "@/components/SiteHeader";
import { WaitlistForm } from "@/components/WaitlistForm";
import styles from "./waitlist.module.css";

export const metadata: Metadata = {
  title: {
    absolute: "Cognilance AI",
  },
  description:
    "Join the Cognilance waitlist for shared agents with human approval, for individuals and teams.",
};

export default function WaitlistPage() {
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
        <section className={styles.section}>
          <div className="container">
            <div className={styles.panel}>
              <p className="eyebrow">Early access</p>
              <h1>Join the waitlist</h1>
              <p className="lead">
                Shared agents with human approval, for individuals and teams.
                Access opens in waves. Tell us who you are and we will invite
                you when a spot opens.
              </p>
              <WaitlistForm />
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </ClickSpark>
  );
}
