import * as React from "react";
import { cn } from "@/lib/utils";

const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("rounded-md border bg-card p-4", className)} {...props} />
  )
);
Card.displayName = "Card";

const CardTitle = React.forwardRef<HTMLHeadingElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h2 ref={ref}
      className={cn("mb-3 text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground", className)}
      {...props} />
  )
);
CardTitle.displayName = "CardTitle";

export { Card, CardTitle };
