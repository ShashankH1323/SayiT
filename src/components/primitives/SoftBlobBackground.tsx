import pastelDecorations from "../../assets/pastel_abstract_decorations.png";
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
        "pointer-events-none absolute inset-0 -z-10 overflow-hidden select-none",
        variant === "full" ? "opacity-80" : "opacity-45",
        className,
      )}
    >
      <img
        src={pastelDecorations}
        alt=""
        className="absolute inset-0 h-full w-full object-cover object-center opacity-70 pointer-events-none"
      />
      <div className="absolute -left-24 -top-28 h-72 w-72 rounded-full bg-blob-purple blur-3xl opacity-50" />
      <div className="absolute -right-20 -top-16 h-64 w-64 rounded-full bg-blob-cyan blur-3xl opacity-50" />
      <div className="absolute -bottom-28 -left-16 h-64 w-64 rounded-full bg-blob-cyan blur-3xl opacity-50" />
      <div className="absolute -bottom-32 -right-24 h-80 w-80 rounded-full bg-blob-pink blur-3xl opacity-50" />
    </div>
  );
}
