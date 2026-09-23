// Say It logo mark: three overlapping rounded organic vertical blobs sharing a
// blue -> violet -> pink -> cyan gradient (per blueprint §4). Reused everywhere.
// useId keeps the SVG gradient id unique so multiple marks on one screen don't collide.
import { useId } from "react";
import { cn } from "../../lib/utils";

export interface SayItMarkProps {
  size?: number;
  className?: string;
}

export function SayItMark({ size = 32, className }: SayItMarkProps) {
  const gid = useId();
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      role="img"
      aria-label="Say It"
      className={cn("shrink-0", className)}
    >
      <defs>
        <linearGradient id={gid} x1="2" y1="4" x2="30" y2="30" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#5A5BFF" />
          <stop offset="0.45" stopColor="#A88BFF" />
          <stop offset="0.78" stopColor="#F0A6E8" />
          <stop offset="1" stopColor="#BFE8F5" />
        </linearGradient>
      </defs>
      <rect x="5" y="9" width="10" height="20" rx="5" fill={`url(#${gid})`} opacity="0.72" transform="rotate(-12 10 19)" />
      <rect x="10.5" y="4" width="11" height="24" rx="5.5" fill={`url(#${gid})`} opacity="0.95" />
      <rect x="17" y="9" width="10" height="20" rx="5" fill={`url(#${gid})`} opacity="0.82" transform="rotate(12 22 19)" />
    </svg>
  );
}
