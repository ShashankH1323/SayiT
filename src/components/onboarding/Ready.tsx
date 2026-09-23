// Onboarding 04 — Ready. Teal success orb + "Ready" pill + hotkey hint from
// settings?.hotkey (fallback "your shortcut"). Full-window (no frame).
// Actions: "Start using Say It" -> finishOnboarding().
import { Check } from "lucide-react";
import { useApp } from "../../lib/appContext";
import { SoftBlobBackground } from "../primitives/SoftBlobBackground";
import { GlassButton } from "../primitives/GlassButton";
import { IconOrb } from "../primitives/IconOrb";
import { StatusPill } from "../primitives/StatusPill";
import { PaginationDots } from "../primitives/PaginationDots";

export function Ready() {
  const { settings, actions } = useApp();
  const hotkey = settings?.hotkey ?? "your shortcut";

  return (
    <div className="relative flex h-full w-full flex-col overflow-hidden bg-canvas-soft">
      <SoftBlobBackground variant="full" />

      <main className="flex flex-1 flex-col items-center justify-center gap-5 px-12 text-center duration-500 animate-in fade-in-0 slide-in-from-bottom-2">
        <div className="relative flex items-center justify-center">
          <div aria-hidden className="absolute h-32 w-32 rounded-full bg-teal-soft opacity-80 blur-2xl" />
          <IconOrb
            icon={<Check size={36} strokeWidth={2} />}
            tone="teal"
            size={88}
            className="relative duration-500 animate-in zoom-in-75"
          />
        </div>

        <div className="flex flex-col items-center gap-3">
          <h1 className="text-display font-display text-ink">You're all set</h1>
          <StatusPill tone="ready" label="Ready" className="rounded-pill glass px-3 py-1" />
        </div>

        <p className="max-w-sm text-body text-secondary">
          Say It is ready to transcribe. Press your shortcut anywhere and start speaking.
        </p>

        <p className="flex flex-wrap items-center justify-center gap-2 text-body text-secondary">
          <span>Press</span>
          <kbd className="rounded-md border border-hairline bg-white/70 px-2 py-1 font-ui text-label text-ink shadow-soft-sm">
            {hotkey}
          </kbd>
          <span>to dictate</span>
        </p>
      </main>

      <footer className="flex flex-col items-center gap-5 pb-9">
        <GlassButton
          variant="primary"
          size="lg"
          className="min-w-[200px]"
          onClick={() => actions.finishOnboarding()}
        >
          Start using Say It
        </GlassButton>
        <PaginationDots count={3} active={2} />
      </footer>
    </div>
  );
}
