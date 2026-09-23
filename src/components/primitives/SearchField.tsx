import { Search } from "lucide-react";
import { cn } from "../../lib/utils";

export interface SearchFieldProps {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  className?: string;
}

/** Glass search input with a leading Lucide Search icon. */
export function SearchField({
  value,
  onChange,
  placeholder = "Search transcripts…",
  className,
}: SearchFieldProps) {
  return (
    <label
      className={cn(
        "glass no-drag flex items-center gap-2 rounded-field px-3 py-2 transition-shadow",
        "focus-within:ring-2 focus-within:ring-accent/60 focus-within:ring-offset-1 focus-within:ring-offset-canvas",
        className,
      )}
    >
      <Search className="h-4 w-4 shrink-0 text-ink-tertiary" strokeWidth={1.75} aria-hidden="true" />
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
        className="w-full min-w-0 bg-transparent text-body text-ink placeholder:text-ink-tertiary focus:outline-none"
      />
    </label>
  );
}
