"use client";

import dynamic from "next/dynamic";
import type { ComponentType } from "react";

const GhostFibers = dynamic(() => import("./GhostFibers"), {
  ssr: false,
}) as unknown as ComponentType<Record<string, unknown>>;

export function HeroFibers() {
  return (
    <GhostFibers
      lightMode
      glowColor="#111111"
      secondaryColor="#737373"
      lineColor="#000000"
      layers={3}
      twist={1.1}
      threads={64}
      fiberStyle="dots"
      depthOfField={0.7}
      hoverEffect="focus"
      intro
      mouseInteraction
      vignette={0.25}
      grain={0.05}
      brightness={0.85}
      glow={0.35}
    />
  );
}
