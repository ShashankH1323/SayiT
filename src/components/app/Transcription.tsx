/* Transcription.tsx — Dedicated Transcription configuration page.
 * Manages Speech Engine (Fast vs High Accuracy vs Local) and explains
 * each Cleanup Mode (Light, Casual, Formal, Structured, Raw) with concrete examples. */
import { Check, Zap, Sparkles, Shield, Cpu, MessageSquareText, FileText, ArrowRight } from "lucide-react";
import { useApp } from "../../lib/appContext";
import { cn } from "../../lib/utils";

interface CleanupCardDef {
  id: string;
  name: string;
  badge: string;
  badgeTone: "teal" | "accent" | "neutral";
  summary: string;
  before: string;
  after: string;
}

const CLEANUP_MODES: CleanupCardDef[] = [
  {
    id: "light",
    name: "Light Cleanup",
    badge: "Recommended • Delete-only",
    badgeTone: "teal",
    summary: "Removes verbal fillers ('um', 'uh', 'you know'), stumbles, and repetitions while strictly preserving your authentic words and natural rhythm.",
    before: "Um so I think you know it's it's ready to ship.",
    after: "I think it's ready to ship.",
  },
  {
    id: "casual",
    name: "Casual",
    badge: "Conversational",
    badgeTone: "accent",
    summary: "Smooths transcripts into natural, relaxed conversational phrasing with smooth contractions and friendly flow.",
    before: "Do not worry we will make sure that it is handled.",
    after: "Don't worry, we'll make sure it's handled.",
  },
  {
    id: "formal",
    name: "Executive Formal",
    badge: "Business Prose",
    badgeTone: "neutral",
    summary: "Elevates spoken thoughts into crisp, professional business prose with articulate sentence structure and clear paragraphs.",
    before: "We gotta fix the login bug asap before release.",
    after: "We must resolve the authentication issue with immediate priority prior to release.",
  },
  {
    id: "structured",
    name: "Structured Notes",
    badge: "Bullets & Key Terms",
    badgeTone: "accent",
    summary: "Distills your thoughts into clean, scannable notes with bullet points and bold key action items.",
    before: "First check the database, second update the API endpoints, and third run the unit tests.",
    after: "• Check the database\n• Update API endpoints\n• Run unit tests",
  },
  {
    id: "raw",
    name: "Raw Verbatim",
    badge: "Untouched",
    badgeTone: "neutral",
    summary: "Exact, literal speech-to-text with zero filler deletion, tone rewriting, or alterations.",
    before: "Um uh like basically what I meant was...",
    after: "Um uh like basically what I meant was...",
  },
];

export function Transcription() {
  const { settings, actions } = useApp();

  if (!settings) return null;

  const isCloud = settings.stt_provider !== "local";
  const isTurbo = settings.groq_model === "whisper-large-v3-turbo";

  return (
    <div className="flex h-full min-h-0 flex-col bg-canvas-soft overflow-x-hidden w-full max-w-full">
      {/* Page Header */}
      <header className="shrink-0 px-6 pb-2 pt-5">
        <h1 className="font-display text-title text-ink">Transcription</h1>
        <p className="mt-0.5 text-body text-ink-secondary">
          Configure recognition speed and intelligent transcript formatting.
        </p>
      </header>

      {/* Scrollable Content */}
      <div className="no-drag min-h-0 flex-1 space-y-5 overflow-y-auto overflow-x-hidden px-6 pb-8 pt-1 w-full max-w-full">
        {/* Section 1: Recognition Engine */}
        <section className="space-y-2.5">
          <h2 className="px-0.5 text-caption font-medium uppercase tracking-wide text-ink-tertiary">
            Recognition Engine
          </h2>

          {/* Engine Type Tabs */}
          <div className="grid grid-cols-2 gap-2.5">
            <button
              type="button"
              onClick={() => actions.setSetting("stt_provider", "groq")}
              className={cn(
                "flex items-center gap-2.5 rounded-card border p-3 text-left transition-all overflow-hidden",
                isCloud
                  ? "border-accent/30 bg-white shadow-soft-sm ring-1 ring-accent/20"
                  : "border-hairline bg-white/50 hover:bg-white text-ink-secondary",
              )}
            >
              <div className={cn(
                "grid h-8 w-8 shrink-0 place-items-center rounded-field",
                isCloud ? "bg-accent-soft text-accent" : "bg-ink/5 text-ink-tertiary"
              )}>
                <Zap className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5 font-medium text-ink text-label truncate">
                  Cloud Engine
                  {isCloud && <span className="h-1.5 w-1.5 rounded-full bg-accent shrink-0" />}
                </div>
                <div className="text-caption text-ink-secondary truncate">
                  Cloud AI
                </div>
              </div>
            </button>

            <button
              type="button"
              onClick={() => actions.setSetting("stt_provider", "local")}
              className={cn(
                "flex items-center gap-2.5 rounded-card border p-3 text-left transition-all overflow-hidden",
                !isCloud
                  ? "border-teal/30 bg-white shadow-soft-sm ring-1 ring-teal/20"
                  : "border-hairline bg-white/50 hover:bg-white text-ink-secondary",
              )}
            >
              <div className={cn(
                "grid h-8 w-8 shrink-0 place-items-center rounded-field",
                !isCloud ? "bg-teal-soft text-teal-deep" : "bg-ink/5 text-ink-tertiary"
              )}>
                <Shield className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5 font-medium text-ink text-label truncate">
                  On-Device Engine
                  {!isCloud && <span className="h-1.5 w-1.5 rounded-full bg-teal shrink-0" />}
                </div>
                <div className="text-caption text-teal-deep font-medium truncate">
                  100% private
                </div>
              </div>
            </button>
          </div>

          {/* Engine Sub-Options */}
          {isCloud ? (
            <div className="grid grid-cols-2 gap-2.5 pt-0.5">
              {/* Fast Option */}
              <button
                type="button"
                onClick={() => actions.setSetting("groq_model", "whisper-large-v3-turbo")}
                className={cn(
                  "relative flex flex-col justify-between rounded-card border p-3.5 text-left transition-all overflow-hidden",
                  isTurbo
                    ? "border-accent/40 bg-white shadow-soft-sm ring-2 ring-accent"
                    : "border-hairline bg-white/60 hover:bg-white",
                )}
              >
                <div>
                  <div className="flex items-center justify-between gap-1.5">
                    <span className="font-medium text-label text-ink">Fast Engine</span>
                    <span className="rounded-pill bg-teal-soft px-1.5 py-0.5 text-[10.5px] font-semibold text-teal-deep">
                      Instant
                    </span>
                  </div>
                  <p className="mt-1 text-caption text-ink-secondary leading-relaxed">
                    Ultra-fast dictation. Built for quick responses and everyday productivity.
                  </p>
                </div>
                {isTurbo && (
                  <span className="mt-2.5 inline-flex items-center gap-1 text-[11px] font-semibold text-accent">
                    <Check className="h-3 w-3" /> Active
                  </span>
                )}
              </button>

              {/* High Accuracy Option */}
              <button
                type="button"
                onClick={() => actions.setSetting("groq_model", "whisper-large-v3")}
                className={cn(
                  "relative flex flex-col justify-between rounded-card border p-3.5 text-left transition-all overflow-hidden",
                  !isTurbo
                    ? "border-accent/40 bg-white shadow-soft-sm ring-2 ring-accent"
                    : "border-hairline bg-white/60 hover:bg-white",
                )}
              >
                <div>
                  <div className="flex items-center justify-between gap-1.5">
                    <span className="font-medium text-label text-ink">High Accuracy</span>
                    <span className="rounded-pill bg-canvas-soft px-1.5 py-0.5 text-[10.5px] font-semibold text-ink-secondary">
                      Detailed
                    </span>
                  </div>
                  <p className="mt-1 text-caption text-ink-secondary leading-relaxed">
                    Maximum precision. Excels at technical terms, dense vocabulary, and accents.
                  </p>
                </div>
                {!isTurbo && (
                  <span className="mt-2.5 inline-flex items-center gap-1 text-[11px] font-semibold text-accent">
                    <Check className="h-3 w-3" /> Active
                  </span>
                )}
              </button>
            </div>
          ) : (
            <div className="flex items-center justify-between rounded-card border border-teal/20 bg-teal-soft/20 p-3.5 shadow-soft-xs">
              <div className="flex items-center gap-3 min-w-0">
                <div className="grid h-9 w-9 shrink-0 place-items-center rounded-field bg-teal-soft text-teal-deep">
                  <Cpu className="h-4 w-4" />
                </div>
                <div className="min-w-0">
                  <div className="text-label font-medium text-ink truncate">
                    100% On-Device: <span className="capitalize">{settings.model}</span>
                  </div>
                  <div className="text-caption text-ink-secondary truncate">
                    Zero network usage. Audio stays on your machine.
                  </div>
                </div>
              </div>
              <button
                type="button"
                onClick={() => actions.navigate("settings-audio")}
                className="shrink-0 inline-flex items-center gap-1 rounded-field border border-hairline bg-white px-2.5 py-1 text-caption font-medium text-ink hover:bg-canvas-soft transition-colors"
              >
                Manage <ArrowRight className="h-3 w-3" />
              </button>
            </div>
          )}
        </section>

        {/* Section 2: Cleanup & Formatting Mode */}
        <section className="space-y-3">
          <div className="flex items-baseline justify-between px-1">
            <h2 className="text-caption font-medium uppercase tracking-wide text-ink-tertiary">
              Cleanup & Formatting Mode
            </h2>
            <span className="text-caption text-ink-secondary">
              Selected: <strong className="capitalize text-ink">{settings.cleanup_mode}</strong>
            </span>
          </div>

          <div className="space-y-2.5">
            {CLEANUP_MODES.map((mode) => {
              const active = settings.cleanup_mode === mode.id;
              return (
                <button
                  key={mode.id}
                  type="button"
                  onClick={() => actions.setSetting("cleanup_mode", mode.id)}
                  className={cn(
                    "w-full rounded-card border p-4 text-left transition-all",
                    active
                      ? "border-accent/40 bg-white shadow-soft-sm ring-2 ring-accent"
                      : "border-hairline bg-white/60 hover:bg-white",
                  )}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <span className="text-label font-semibold text-ink">{mode.name}</span>
                      <span
                        className={cn(
                          "rounded-pill px-2 py-0.5 text-[11px] font-medium",
                          mode.badgeTone === "teal"
                            ? "bg-teal-soft text-teal-deep"
                            : mode.badgeTone === "accent"
                              ? "bg-accent-soft text-accent"
                              : "bg-canvas-soft text-ink-secondary",
                        )}
                      >
                        {mode.badge}
                      </span>
                    </div>
                    {active ? (
                      <span className="grid h-5 w-5 place-items-center rounded-full bg-accent text-white shadow-soft-sm">
                        <Check className="h-3 w-3" strokeWidth={2.5} />
                      </span>
                    ) : (
                      <span className="h-5 w-5 rounded-full border border-hairline" />
                    )}
                  </div>

                  <p className="mt-1.5 text-caption text-ink-secondary leading-relaxed">
                    {mode.summary}
                  </p>

                  {/* Concrete Before -> After Example */}
                  <div className="mt-2 rounded-field bg-canvas-soft p-2.5 text-[11.5px] font-sans overflow-hidden w-full">
                    <div className="flex items-start gap-2 text-ink-tertiary min-w-0">
                      <span className="shrink-0 font-medium text-ink-tertiary">Spoken:</span>
                      <span className="italic break-words min-w-0 flex-1">"{mode.before}"</span>
                    </div>
                    <div className="mt-1 flex items-start gap-2 text-ink min-w-0">
                      <span className="shrink-0 font-semibold text-teal-deep">Output:</span>
                      <span className="font-medium whitespace-pre-line break-words min-w-0 flex-1">{mode.after}</span>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </section>
      </div>
    </div>
  );
}
