import { Check } from "lucide-react";
import { useApp } from "../../lib/appContext";
import { SoftBlobBackground } from "../primitives/SoftBlobBackground";
import { GlassButton } from "../primitives/GlassButton";
import { IconOrb } from "../primitives/IconOrb";
import { PaginationDots } from "../primitives/PaginationDots";
import { formatHotkeyDisplay } from "../../lib/hotkeyUtils";

export function Ready() {
  const { settings, actions } = useApp();
  const hotkey = settings?.hotkey ? formatHotkeyDisplay(settings.hotkey) : "Ctrl + Space";

  return (
    <div className="relative flex h-full w-full flex-col overflow-hidden bg-canvas-soft select-none">
      <SoftBlobBackground variant="full" />

      <main className="flex flex-1 flex-col items-center justify-center gap-5 px-10 text-center duration-500 animate-in fade-in-0 slide-in-from-bottom-2">
        <div className="relative flex items-center justify-center">
          <div aria-hidden className="absolute h-32 w-32 rounded-full bg-accent-soft opacity-80 blur-2xl" />
          <IconOrb
            icon={<Check size={36} strokeWidth={2.5} />}
            tone="accent"
            size={88}
            className="relative duration-500 animate-in zoom-in-75 text-white"
          />
        </div>

        <div className="flex flex-col items-center gap-2">
          <h1 className="text-display font-display font-bold text-ink">You're all set!</h1>
          <p className="max-w-xs text-body text-ink-secondary leading-relaxed">
            Say It is ready to transcribe. Use <strong className="text-ink font-semibold">{hotkey}</strong> and start speaking.
          </p>
        </div>
      </main>

      <footer className="flex flex-col items-center gap-4 pb-8">
        <GlassButton
          variant="primary"
          size="lg"
          className="min-w-[200px] text-label font-semibold shadow-soft-md"
          onClick={() => actions.finishOnboarding()}
        >
          Open app
        </GlassButton>
        <PaginationDots count={4} active={3} />
      </footer>
    </div>
  );
}
