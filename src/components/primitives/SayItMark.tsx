import logoMark from "../../assets/brand_logo_mark.png";
import { cn } from "../../lib/utils";

export interface SayItMarkProps {
  size?: number;
  className?: string;
}

export function SayItMark({ size = 32, className }: SayItMarkProps) {
  return (
    <img
      src={logoMark}
      alt="Say It"
      width={size}
      height={size}
      className={cn("shrink-0 object-contain select-none pointer-events-none drop-shadow-sm", className)}
      style={{ width: `${size}px`, height: `${size}px` }}
      draggable={false}
    />
  );
}
