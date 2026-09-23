// Ambient pastel gradient blobs behind content. Deterministic fixed geometry
// (per blueprint §4) — not a random generator. Decorative, non-interactive.
import { cn } from "../../lib/utils";

export interface SoftBlobBackgroundProps {
  className?: string;
  variant?: "full" | "subtle";
}

export function SoftBlobBackground({ className, variant = "full" }: SoftBlobBackgroundProps) {
  return (
    <div
      aria-hidden
      className={cn(
        "pointer-events-none absolute inset-0 -z-10 overflow-hidden",
        variant === "full" ? "opacity-70" : "opacity-35",
        className,
      )}
    >
      <div className="absolute -left-24 -top-28 h-72 w-72 rounded-full bg-blob-purple blur-3xl" />
      <div className="absolute -right-20 -top-16 h-64 w-64 rounded-full bg-blob-cyan blur-3xl" />
      <div className="absolute -bottom-28 -left-16 h-64 w-64 rounded-full bg-blob-cyan blur-3xl" />
      <div className="absolute -bottom-32 -right-24 h-80 w-80 rounded-full bg-blob-pink blur-3xl" />
    </div>
  );
}
