// Onboarding 02 — Welcome. Brand + value prop + 3 feature bullets (hero art is
// the blob system + IconOrbs, no stock illustration). Full-window (no frame).
// Actions: "Get started" -> setOnboarding("permissions").
import { Mic, Zap, ShieldCheck, ArrowRight } from "lucide-react";
import { useApp } from "../../lib/appContext";
import { SoftBlobBackground } from "../primitives/SoftBlobBackground";
import { SayItMark } from "../primitives/SayItMark";
import { GlassButton } from "../primitives/GlassButton";
import { IconOrb } from "../primitives/IconOrb";
import { PaginationDots } from "../primitives/PaginationDots";

const FEATURES = [
  { Icon: Mic, tone: "accent", title: "Speak naturally", desc: "Dictate into any app with a single shortcut." },
  { Icon: Zap, tone: "accent", title: "Fast & local", desc: "Runs on your device — transcripts in seconds." },
  { Icon: ShieldCheck, tone: "teal", title: "Always private", desc: "Your voice never leaves your machine." },
] as const;

export function Welcome() {
  const { actions } = useApp();

  return (
    <div className="relative flex h-full w-full flex-col overflow-hidden bg-canvas-soft">
      <SoftBlobBackground variant="full" />

      <main className="flex flex-1 flex-col items-center justify-center gap-6 px-12 text-center duration-500 animate-in fade-in-0 slide-in-from-bottom-2">
        <div className="relative flex items-center justify-center">
          <div aria-hidden className="absolute h-28 w-28 rounded-full bg-accent-soft opacity-70 blur-2xl" />
          <SayItMark size={68} className="relative" />
        </div>

        <div className="flex flex-col items-center gap-1.5">
          <h1 className="text-display font-display text-ink">Welcome to Say It</h1>
          <p className="text-body text-secondary">Fast · Private · Always with you</p>
        </div>

        <ul className="mt-1 flex w-full max-w-sm flex-col gap-3.5 text-left">
          {FEATURES.map((f) => (
            <li key={f.title} className="flex items-center gap-3.5">
              <IconOrb icon={<f.Icon size={20} strokeWidth={1.75} />} tone={f.tone} size={44} />
              <div className="flex flex-col">
                <span className="text-label font-semibold text-ink">{f.title}</span>
                <span className="text-caption text-ink-tertiary">{f.desc}</span>
              </div>
            </li>
          ))}
        </ul>
      </main>

      <footer className="flex flex-col items-center gap-5 pb-9">
        <GlassButton
          variant="primary"
          size="lg"
          className="min-w-[200px]"
          iconRight={<ArrowRight size={18} strokeWidth={2} />}
          onClick={() => actions.setOnboarding("permissions")}
        >
          Get started
        </GlassButton>
        <PaginationDots count={3} active={0} />
      </footer>
    </div>
  );
}
