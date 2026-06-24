import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide transition-colors",
  {
    variants: {
      variant: {
        pending: "border-border text-muted bg-surface/50",
        running: "border-planner/40 text-planner bg-planner/10",
        done: "border-genui/40 text-genui bg-genui/10",
        fallback: "border-thinking/40 text-thinking bg-thinking/10",
        idle: "border-border text-muted bg-surface/50",
        executing: "border-registry/40 text-registry bg-registry/10",
      },
    },
    defaultVariants: { variant: "pending" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
