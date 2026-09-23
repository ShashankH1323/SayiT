// Onboarding 03 — Permissions. Informational only (no bridge permission call).
// Shows the detected mic from useApp().devices[0] when present. Full-window.
// Actions: "Continue" -> setOnboarding("ready"); "Back" -> setOnboarding("welcome").
import { Mic, ArrowLeft } from "lucide-react";
import { useApp } from "../../lib/appContext";
import { SoftBlobBackground } from "../primitives/SoftBlobBackground";
import { GlassButton } from "../primitives/GlassButton";
import { IconOrb } from "../primitives/IconOrb";
import { PaginationDots } from "../primitives/PaginationDots";

export function Permissions() {
  const { devices, actions } = useApp();
  const mic = devices && devices.length > 0 ? devices[0] : null;

  return (
    <div className="relative flex h-full w-full flex-col overflow-hidden bg-canvas-soft">
      <SoftBlobBackground variant="full" />

      <main className="flex flex-1 flex-col items-center justify-center gap-5 px-12 text-center duration-500 animate-in fade-in-0 slide-in-from-bottom-2">
        <div className="relative flex items-center justify-center">
          <div aria-hidden className="absolute h-32 w-32 rounded-full bg-accent-soft opacity-70 blur-2xl" />
          <IconOrb icon={<Mic size={32} strokeWidth={1.75} />} tone="accent" size={88} className="relative" />
        </div>

        <div className="flex flex-col items-center gap-2">
          <h1 className="text-display font-display text-ink">Microphone access</h1>
          <p className="max-w-sm text-body text-secondary">
            Say It listens through your microphone to transcribe what you say. Audio is processed
            locally and never leaves your device.
          </p>
        </div>

        {mic && (
          <span className="inline-flex items-center gap-2 rounded-pill glass px-3.5 py-1.5 text-caption text-secondary">
            <span aria-hidden className="h-1.5 w-1.5 shrink-0 rounded-pill bg-teal" />
            Detected: <span className="font-medium text-ink">{mic}</span>
          </span>
        )}
      </main>

      <footer className="flex flex-col items-center gap-3 pb-9">
        <GlassButton
          variant="primary"
          size="lg"
          className="min-w-[200px]"
          onClick={() => actions.setOnboarding("ready")}
        >
          Continue
        </GlassButton>
        <GlassButton
          variant="ghost"
          size="sm"
          icon={<ArrowLeft size={16} strokeWidth={2} />}
          onClick={() => actions.setOnboarding("welcome")}
        >
          Back
        </GlassButton>
        <PaginationDots count={3} active={1} className="mt-2" />
      </footer>
    </div>
  );
}
