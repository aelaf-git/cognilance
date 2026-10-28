"use client"

import { FC } from "react"

interface BrandProps {
  theme?: "dark" | "light"
}

export const Brand: FC<BrandProps> = ({ theme = "dark" }) => {
  return (
    <div className="flex flex-col items-center">
      <img
        src="/brand/Cognilance-Logo.png"
        alt="Cognilance"
        className="mb-3 size-16 object-contain"
        data-theme={theme}
      />
      <div className="brand-wordmark text-3xl text-foreground">Cognilance</div>
    </div>
  )
}
