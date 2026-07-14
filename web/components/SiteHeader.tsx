import Image from "next/image";
import styles from "./SiteHeader.module.css";

export function SiteHeader() {
  return (
    <header className={styles.header}>
      <div className={`container ${styles.inner}`}>
        <a href="#top" className={styles.brand}>
          <Image src="/logo.png" alt="" width={28} height={28} />
          <span>Cognilance</span>
        </a>
        <nav className={styles.nav} aria-label="Primary">
          <a href="#product">Product</a>
          <a href="#how">How it works</a>
          <a href="#team">Team</a>
        </nav>
        <a href="#waitlist" className={`btn btnPrimary ${styles.cta}`}>
          Join the beta
        </a>
      </div>
    </header>
  );
}
