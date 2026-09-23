// Circular glass shell around a Lucide icon. Icon inherits currentColor via tone.
import type { ReactNode } from "react";
import { cn } from "../../lib/utils";

export interface IconOrbProps {
  icon: ReactNode;
  tone?: "accent" | "teal" | "neutral";
  size?: number;
  className?: string;
}

const TONE = {
  accent: "text-accent ring-1 ring-accent/15",
  teal: "text-teal-deep ring-1 ring-teal/15",
  neutral: "text-ink-secondary ring-1 ring-hairline",
} as const;

export function IconOrb({ icon, tone = "accent", size = 64, className }: IconOrbProps) {
  return (
    <div
      style={{ width: size, height: size }}
      className={cn("glass flex items-center justify-center rounded-full", TONE[tone], className)}
    >
      <span className="inline-flex items-center justify-center">{icon}</span>
    </div>
  );
}
