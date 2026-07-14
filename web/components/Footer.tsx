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
          <a href="#waitlist">Join beta</a>
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
