/* SettingsShell — shared header + General|Audio tab bar + scrollable inner
 * region for the two settings screens, plus the controls/labels both reuse
 * (SelectField, humanize, langLabel). Consumer-only: reads route + navigate
 * from useApp(). The app shell owns the window chrome and ambient blobs, so
 * this pane stays a clean light surface. */
import type { ReactNode, SelectHTMLAttributes } from "react";
import { ChevronDown } from "lucide-react";
import { useApp } from "../../lib/appContext";
import { cn } from "../../lib/utils";

const TABS = [
  { route: "settings-general", label: "General" },
  { route: "settings-audio", label: "Audio" },
] as const;

export function SettingsShell({ children }: { children: ReactNode }) {
  const { route, actions } = useApp();
  return (
    <div className="flex h-full min-h-0 flex-col bg-canvas-soft">
      <header className="shrink-0 px-6 pb-3 pt-5">
        <h1 className="font-display text-title text-ink">Settings</h1>
        <div
          role="group"
          aria-label="Settings sections"
          className="no-drag mt-3 inline-flex gap-1 rounded-field border border-hairline bg-canvas-soft p-1"
        >
          {TABS.map((t) => {
            const active = route === t.route;
            return (
              <button
                key={t.route}
                type="button"
                aria-current={active ? "page" : undefined}
                onClick={() => actions.navigate(t.route)}
                className={cn(
                  "h-8 rounded-[10px] px-4 text-label transition-colors",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1",
                  active ? "bg-white text-accent shadow-soft-sm" : "text-ink-secondary hover:text-ink",
                )}
              >
                {t.label}
              </button>
            );
          })}
        </div>
      </header>
      <div className="no-drag min-h-0 flex-1 space-y-5 overflow-y-auto px-6 pb-6 pt-1">
        {children}
      </div>
    </div>
  );
}

/** Group label + soft-glass panel that hosts a run of SettingRows. */
export function SettingsSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h2 className="mb-1.5 px-1 text-caption font-medium uppercase tracking-wide text-ink-tertiary">
        {title}
      </h2>
      <div className="rounded-card border border-hairline bg-white/60 px-4 shadow-soft-sm">
        {children}
      </div>
    </section>
  );
}

export type Opt = string | { value: string; label: string };
const toOpt = (o: Opt) => (typeof o === "string" ? { value: o, label: o } : o);

export interface SelectFieldProps
  extends Omit<SelectHTMLAttributes<HTMLSelectElement>, "onChange" | "value"> {
  value: string;
  options: Opt[];
  onValueChange: (v: string) => void;
  "aria-label": string;
}

/** Native <select> styled to the token system, with a custom chevron. */
export function SelectField({ value, options, onValueChange, className, ...rest }: SelectFieldProps) {
  return (
    <div className="relative inline-flex">
      <select
        value={value}
        onChange={(e) => onValueChange(e.target.value)}
        className={cn(
          "no-drag h-9 w-36 cursor-pointer appearance-none rounded-field border border-hairline bg-white pl-3 pr-8 text-label text-ink truncate",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1",
          className,
        )}
        {...rest}
      >
        {options.map(toOpt).map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      <ChevronDown
        aria-hidden
        className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-tertiary"
      />
    </div>
  );
}

/** Light skeleton shown before settings/options have loaded. */
export function SettingsLoading() {
  return (
    <div className="space-y-3" aria-busy="true" aria-live="polite">
      {[0, 1, 2].map((i) => (
        <div key={i} className="h-20 animate-pulse rounded-card border border-hairline bg-white/50" />
      ))}
      <span className="sr-only">Loading settings…</span>
    </div>
  );
}

/* ---- label helpers (raw option codes -> human text) ---- */
const LANGS: Record<string, string> = {
  auto: "Auto-detect", en: "English", es: "Spanish", fr: "French", de: "German",
  hi: "Hindi", kn: "Kannada", te: "Telugu", ta: "Tamil", mr: "Marathi",
  bn: "Bengali", gu: "Gujarati", ja: "Japanese", zh: "Chinese",
};
export const langLabel = (code: string) => LANGS[code] ?? code.toUpperCase();

const SPECIAL: Record<string, string> = {
  ctrl_v: "Ctrl + V", ctrl_shift_v: "Ctrl + Shift + V",
  groq: "Groq · Cloud", local: "Local · GPU",
  cuda: "GPU (CUDA)", cpu: "CPU",
};
export function humanize(v: string): string {
  if (SPECIAL[v]) return SPECIAL[v];
  return v.replace(/[_-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
