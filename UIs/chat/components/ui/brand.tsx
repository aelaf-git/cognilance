"use client"

import { FC } from "react"

interface BrandProps {
  theme?: "dark" | "light"
}

export const Brand: FC<BrandProps> = ({ theme = "dark" }) => {
  const src = theme === "light" ? "/icon-light.png" : "/icon.png"

  return (
    <div className="flex flex-col items-center">
      <img
        src={src}
        alt="Cognilance"
        className="mb-2 h-16 w-16 object-contain"
      />
      <div className="text-4xl font-bold tracking-wide">Cognilance</div>
    </div>
  )
}
