// Screen 14 — About. Renders inside the app shell. Consumer only: reads
// settings.hotkey via useApp(); no bridge version call exists, so the version
// string is static. Composition: centered brand block, a "what it is" blurb
// with value bullets, the live hotkey hint, and placeholder footer links.
import { Shield, Zap, Globe, Github, BookOpen } from "lucide-react";
import { useApp } from "../../lib/appContext";
import { SayItMark } from "../primitives/SayItMark";
import { SayItWordmark } from "../primitives/SayItWordmark";
import { IconOrb } from "../primitives/IconOrb";
import { GlassButton } from "../primitives/GlassButton";
import { SoftBlobBackground } from "../primitives/SoftBlobBackground";

// Value props shown as IconOrb bullets. `as const` keeps `tone` a literal so it
// satisfies IconOrb's tone union.
const VALUES = [
  { Icon: Shield, tone: "accent", title: "Private & local", body: "Audio and transcripts never leave your device." },
  { Icon: Zap, tone: "teal", title: "Fast", body: "Real-time dictation, transcribed in seconds." },
  { Icon: Globe, tone: "accent", title: "Multilingual", body: "Speak many languages and paste anywhere." },
] as const;

export function About() {
  const { settings } = useApp();
  const hotkey = settings?.hotkey ?? "Ctrl + Win"; // settings null until bridge is live

  return (
    // isolate: give SoftBlobBackground's -z-10 a local stacking context so the
    // blobs sit above this section's canvas fill, not behind it.
    <section className="relative isolate flex h-full flex-col overflow-hidden bg-canvas-soft">
      <SoftBlobBackground variant="subtle" />

      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto flex min-h-full max-w-md flex-col items-center justify-center gap-7 px-8 py-10 text-center">
          {/* Brand block */}
          <div className="flex flex-col items-center gap-3">
            <SayItMark size={76} />
            <SayItWordmark size="lg" />
            <p className="text-caption text-ink-tertiary">Say It · v1.0</p>
            <p className="font-hand text-2xl leading-none text-accent">Fast · Private · Always with you</p>
          </div>

          {/* What it is + value bullets */}
          <div className="glass w-full rounded-card p-5 text-left">
            <p className="text-body text-secondary">
              Say It turns your voice into text right on your machine — local, private, real-time
              dictation you can paste into any app.
            </p>
            <ul className="mt-4 flex flex-col gap-3">
              {VALUES.map((v) => (
                <li key={v.title} className="flex items-center gap-3">
                  <IconOrb icon={<v.Icon size={18} strokeWidth={2} />} tone={v.tone} size={40} />
                  <div>
                    <p className="text-label font-semibold text-ink">{v.title}</p>
                    <p className="text-caption text-ink-tertiary">{v.body}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>

          {/* Live hotkey hint */}
          <p className="text-caption text-secondary">
            Press{" "}
            <kbd className="mx-0.5 inline-flex items-center rounded-md border border-hairline bg-white/70 px-2 py-0.5 font-ui text-caption font-medium text-ink shadow-soft-sm">
              {hotkey}
            </kbd>{" "}
            anywhere to dictate.
          </p>

          {/* Footer links — placeholders, no external nav wired */}
          <div className="flex items-center gap-3">
            <GlassButton variant="ghost" size="sm" icon={<Github size={16} strokeWidth={2} />}>
              GitHub
            </GlassButton>
            <GlassButton variant="ghost" size="sm" icon={<BookOpen size={16} strokeWidth={2} />}>
              Docs
            </GlassButton>
          </div>
        </div>
      </div>
    </section>
  );
}
