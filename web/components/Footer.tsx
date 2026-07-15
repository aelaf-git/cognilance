import Image from "next/image";
import styles from "./Footer.module.css";

export function Footer() {
  return (
    <footer className={styles.footer}>
      <div className={`container ${styles.inner}`}>
        <div className={styles.brandBlock}>
          <Image src="/logo.png" alt="" width={24} height={24} />
          <div>
            <p className={styles.brand}>Cognilance</p>
            <p className={styles.meta}>Marketplace of Minds · Currently in beta</p>
          </div>
        </div>
        <div className={styles.links}>
          <a href="#product">Product</a>
          <a href="#how">How it works</a>
          <a
            href="https://docs.google.com/forms/d/e/1FAIpQLScV72qv_wHi7nWeNXm76kjI9lYYKV740lULDBs6nWH0xuALnQ/viewform?usp=publish-editor"
            target="_blank"
            rel="noreferrer"
          >
            Join the waitlist
          </a>
          <a href="https://github.com/aelaf-git/cognilance" target="_blank" rel="noreferrer">
            Developer docs
          </a>
        </div>
        <p className={styles.copy}>
          © {new Date().getFullYear()} Cognilance. All rights reserved.
        </p>
      </div>
    </footer>
  );
}
