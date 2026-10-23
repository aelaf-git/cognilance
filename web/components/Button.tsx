import type { ReactNode } from "react";

type ButtonProps = {
  href: string;
  children: ReactNode;
  hoverText?: string;
  variant?: "primary" | "ghost";
  className?: string;
  external?: boolean;
  onClick?: () => void;
};

export function Button({
  href,
  children,
  hoverText,
  variant = "primary",
  className = "",
  external,
  onClick,
}: ButtonProps) {
  const label = typeof children === "string" ? children : hoverText ?? "";
  const hover = hoverText ?? label;
  const classes = `btn ${variant === "ghost" ? "btnGhost" : "btnPrimary"} ${className}`.trim();
  const content = (
    <span className="btnText">
      <span>{children}</span>
      <span aria-hidden="true">{hover}</span>
    </span>
  );

  if (external) {
    return (
      <a
        href={href}
        className={classes}
        target="_blank"
        rel="noreferrer"
        onClick={onClick}
      >
        {content}
      </a>
    );
  }

  return (
    <a href={href} className={classes} onClick={onClick}>
      {content}
    </a>
  );
}
