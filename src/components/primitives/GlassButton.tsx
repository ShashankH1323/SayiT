// Rounded button: accent primary, glass secondary, transparent ghost.
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "../../lib/utils";

export interface GlassButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md" | "lg";
  icon?: ReactNode;
  iconRight?: ReactNode;
  children?: ReactNode;
}

const VARIANT = {
  primary: "bg-accent text-white hover:bg-accent-deep shadow-soft-sm",
  secondary: "glass text-ink hover:bg-white",
  ghost: "bg-transparent text-ink hover:bg-accent-soft",
} as const;

const SIZE = {
  sm: "h-8 px-3 text-caption gap-1.5",
  md: "h-10 px-4 text-label gap-2",
  lg: "h-11 px-5 text-body gap-2",
} as const;

export function GlassButton({
  variant = "primary",
  size = "md",
  icon,
  iconRight,
  children,
  className,
  type = "button",
  ...props
}: GlassButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        "inline-flex select-none items-center justify-center rounded-field font-ui font-medium transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2",
        "disabled:pointer-events-none disabled:opacity-50",
        VARIANT[variant],
        SIZE[size],
        className,
      )}
      {...props}
    >
      {icon && <span className="inline-flex shrink-0 items-center">{icon}</span>}
      {children}
      {iconRight && <span className="inline-flex shrink-0 items-center">{iconRight}</span>}
    </button>
  );
}
