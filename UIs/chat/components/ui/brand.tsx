"use client"

import { FC } from "react"

interface BrandProps {
  theme?: "dark" | "light"
}

export const Brand: FC<BrandProps> = ({ theme = "dark" }) => {
  return (
    <div className="flex flex-col items-center">
      <img
        src="/cognilance-logo.png"
        alt="Cognilance"
        className="mb-2 h-16 w-16 object-contain"
        data-theme={theme}
      />
      <div className="text-4xl font-bold tracking-wide">Cognilance</div>
    </div>
  )
}
