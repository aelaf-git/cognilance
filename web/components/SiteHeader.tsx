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
        <a
          href="https://docs.google.com/forms/d/e/1FAIpQLScV72qv_wHi7nWeNXm76kjI9lYYKV740lULDBs6nWH0xuALnQ/viewform?usp=publish-editor"
          className={`btn btnPrimary ${styles.cta}`}
          target="_blank"
          rel="noreferrer"
        >
          Join the waitlist
        </a>
      </div>
    </header>
  );
}
