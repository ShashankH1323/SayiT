import { useState } from "react";
import { Shield, RefreshCw, MessageSquare, ChevronRight, Check } from "lucide-react";
import { useApp } from "../../lib/appContext";
import { SayItMark } from "../primitives/SayItMark";
import { SoftBlobBackground } from "../primitives/SoftBlobBackground";
import { formatHotkeyDisplay } from "../../lib/hotkeyUtils";
import thinkItSlogan from "../../assets/handwritten_think_it_say_it_done.png";

export function About() {
  const { settings } = useApp();
  const hotkey = settings?.hotkey ?? "ctrl+space";
  const [updateStatus, setUpdateStatus] = useState<string | null>(null);

  const handleCheckUpdate = () => {
    setUpdateStatus("checking");
    setTimeout(() => {
      setUpdateStatus("latest");
      setTimeout(() => setUpdateStatus(null), 3000);
    }, 1200);
  };

  return (
    <section className="relative isolate flex h-full flex-col overflow-hidden bg-canvas-soft select-none">
      <SoftBlobBackground variant="subtle" />

      {/* Page Header */}
      <header className="shrink-0 px-6 pt-5">
        <h1 className="font-display text-title font-bold text-ink">About</h1>
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-4">
        <div className="mx-auto flex min-h-full max-w-md flex-col items-center justify-center gap-6 text-center">
          {/* Brand hero block matching Card 14 */}
          <div className="flex flex-col items-center gap-3">
            <SayItMark size={84} className="drop-shadow-lg" />
            <div className="space-y-0.5">
              <h2 className="font-display text-2xl font-bold tracking-tight text-ink">Say It</h2>
              <p className="text-caption font-medium text-ink-tertiary">Version 1.0.0</p>
            </div>
          </div>

          {/* Action options card list matching Card 14 */}
          <div className="w-full space-y-2 text-left">
            <button
              type="button"
              onClick={handleCheckUpdate}
              className="flex w-full items-center justify-between rounded-card border border-hairline bg-white/80 backdrop-blur-md p-3.5 shadow-soft-xs hover:border-accent/30 hover:bg-white hover:shadow-soft-sm transition-all"
            >
              <div className="flex items-center gap-3">
                <div className="grid h-8 w-8 place-items-center rounded-field bg-accent-soft text-accent">
                  <RefreshCw className={updateStatus === "checking" ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
                </div>
                <div>
                  <div className="text-label font-medium text-ink">Check for updates</div>
                  <div className="text-caption text-ink-tertiary">
                    {updateStatus === "checking"
                      ? "Checking release channel…"
                      : updateStatus === "latest"
                        ? "Say It is up to date"
                        : "Current version: 1.0.0"}
                  </div>
                </div>
              </div>
              {updateStatus === "latest" ? (
                <span className="inline-flex items-center gap-1 text-caption font-semibold text-teal-deep">
                  <Check className="h-4 w-4 text-teal" /> Up to date
                </span>
              ) : (
                <ChevronRight className="h-4 w-4 text-ink-tertiary" />
              )}
            </button>

            <a
              href="mailto:support@sayit.app?subject=Say%20It%20Feedback"
              className="flex w-full items-center justify-between rounded-card border border-hairline bg-white/80 backdrop-blur-md p-3.5 shadow-soft-xs hover:border-accent/30 hover:bg-white hover:shadow-soft-sm transition-all"
            >
              <div className="flex items-center gap-3">
                <div className="grid h-8 w-8 place-items-center rounded-field bg-teal-soft text-teal-deep">
                  <MessageSquare className="h-4 w-4" />
                </div>
                <div>
                  <div className="text-label font-medium text-ink">Send feedback</div>
                  <div className="text-caption text-ink-tertiary">Share thoughts or feature requests</div>
                </div>
              </div>
              <ChevronRight className="h-4 w-4 text-ink-tertiary" />
            </a>

            <div className="flex w-full items-center justify-between rounded-card border border-hairline bg-white/80 backdrop-blur-md p-3.5 shadow-soft-xs">
              <div className="flex items-center gap-3">
                <div className="grid h-8 w-8 place-items-center rounded-field bg-ink/5 text-ink-secondary">
                  <Shield className="h-4 w-4" />
                </div>
                <div>
                  <div className="text-label font-medium text-ink">Privacy policy</div>
                  <div className="text-caption text-ink-tertiary">100% on-device private audio processing</div>
                </div>
              </div>
              <span className="text-[11px] font-semibold text-teal-deep bg-teal-soft px-2 py-0.5 rounded-pill">
                Local first
              </span>
            </div>
          </div>

          {/* Live hotkey hint */}
          <p className="text-caption text-ink-tertiary">
            Press{" "}
            <kbd className="mx-1 inline-flex items-center rounded-md border border-hairline bg-white px-2 py-0.5 font-ui text-caption font-semibold text-ink shadow-soft-xs">
              {formatHotkeyDisplay(hotkey)}
            </kbd>{" "}
            anywhere to dictate.
          </p>

          {/* Slogan handwritten flourish from Final Ui */}
          <div className="pt-2 opacity-85 select-none pointer-events-none">
            <img
              src={thinkItSlogan}
              alt="Think it. Say it. Done."
              className="h-12 w-auto object-contain"
              draggable={false}
            />
          </div>
        </div>
      </div>
    </section>
  );
}
