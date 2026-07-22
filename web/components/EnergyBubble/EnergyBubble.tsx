"use client";

import dynamic from "next/dynamic";
import styles from "./EnergyBubble.module.css";

const BinarySphereCanvas = dynamic(() => import("./BinarySphereCanvas"), {
  ssr: false,
  loading: () => <div className={styles.fallback} aria-hidden="true" />,
});

export type EnergyBubbleProps = {
  className?: string;
  /** Visual size preset for reuse outside the hero */
  size?: "sm" | "md" | "lg";
};

export function EnergyBubble({ className = "", size = "lg" }: EnergyBubbleProps) {
  return (
    <div
      className={`${styles.stage} ${styles[size]} ${className}`.trim()}
      aria-hidden="true"
    >
      <div className={styles.glow} />
      <BinarySphereCanvas />
    </div>
  );
}

export default EnergyBubble;
