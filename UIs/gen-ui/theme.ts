import { useEffect, useState, type CSSProperties } from "react";

export type BrandColors = {
  background: string;
  surface: string;
  border: string;
  foreground: string;
  muted: string;
  dim: string;
  ember: string;
  planner: string;
  white: string;
};

/** Light and dark brand tokens. */
export const lightColors: BrandColors = {
  background: "hsl(40 20% 97%)",
  surface: "hsl(0 0% 100%)",
  border: "hsl(266 12% 86%)",
  foreground: "hsl(266 30% 12%)",
  muted: "hsl(266 8% 42%)",
  dim: "hsl(266 6% 55%)",
  ember: "hsl(8 100% 59%)",
  planner: "hsl(29 98% 57%)",
  white: "#ffffff",
};

export const darkColors: BrandColors = {
  background: "hsl(266 45% 6%)",
  surface: "hsl(260 22% 11%)",
  border: "hsl(260 10% 18%)",
  foreground: "hsl(0 0% 98%)",
  muted: "hsl(0 0% 78%)",
  dim: "hsl(0 0% 60%)",
  ember: "hsl(8 100% 59%)",
  planner: "hsl(29 98% 57%)",
  white: "#ffffff",
};

export function readBrandColors(): BrandColors {
  if (typeof document === "undefined") return darkColors;
  return document.documentElement.classList.contains("dark") ? darkColors : lightColors;
}

export function useBrandColors(): BrandColors {
  const [colors, setColors] = useState<BrandColors>(readBrandColors);

  useEffect(() => {
    const sync = () => setColors(readBrandColors());
    sync();
    const observer = new MutationObserver(sync);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  return colors;
}

export function cardStyle(colors: BrandColors): CSSProperties {
  return {
    width: "100%",
    maxWidth: 720,
    border: `1px solid ${colors.border}`,
    borderRadius: 12,
    overflow: "hidden",
    fontFamily: '"IBM Plex Sans", system-ui, sans-serif',
    background: colors.surface,
    color: colors.foreground,
  };
}

export function headerStyle(colors: BrandColors): CSSProperties {
  return {
    background: `linear-gradient(90deg,${colors.planner},${colors.ember})`,
    color: colors.white,
    padding: "12px 16px",
    fontWeight: 600,
    fontFamily: '"Space Grotesk", system-ui, sans-serif',
  };
}

export function insetBoxStyle(colors: BrandColors): CSSProperties {
  return {
    margin: 0,
    padding: 12,
    background: colors.background,
    borderRadius: 8,
    border: `1px solid ${colors.border}`,
    lineHeight: 1.5,
    overflow: "auto",
    color: colors.foreground,
  };
}
