import { ArrowRight } from "lucide-react";
import { useApp } from "../../lib/appContext";
import { SoftBlobBackground } from "../primitives/SoftBlobBackground";
import { GlassButton } from "../primitives/GlassButton";
import { PaginationDots } from "../primitives/PaginationDots";
import welcomeCharacters from "../../assets/welcome_group_characters.png";

export function Welcome() {
  const { actions } = useApp();

  return (
    <div className="relative flex h-full w-full flex-col overflow-hidden bg-canvas-soft select-none">
      <SoftBlobBackground variant="full" />

      <main className="flex flex-1 flex-col items-center justify-center gap-5 px-8 text-center duration-500 animate-in fade-in-0 slide-in-from-bottom-2">
        <h1 className="text-display font-display font-bold text-ink">Welcome to Say It</h1>

        {/* Hero Character Illustration from Final Ui.png Card 2 */}
        <div className="relative my-1 max-w-sm overflow-hidden rounded-2xl">
          <img
            src={welcomeCharacters}
            alt="Say It Community"
            className="h-auto w-full object-contain drop-shadow-md select-none pointer-events-none"
            draggable={false}
          />
        </div>

        <div className="flex flex-col items-center gap-1.5 max-w-xs">
          <p className="text-body font-medium text-ink-secondary leading-relaxed">
            Turn your voice into text. Faster. Easier. Everywhere.
          </p>
        </div>
      </main>

      <footer className="flex flex-col items-center gap-4 pb-8">
        <GlassButton
          variant="primary"
          size="lg"
          className="min-w-[210px] text-label font-semibold shadow-soft-md"
          iconRight={<ArrowRight size={18} strokeWidth={2} />}
          onClick={() => actions.setOnboarding("permissions")}
        >
          Let's get started
        </GlassButton>
        <PaginationDots count={4} active={0} />
      </footer>
    </div>
  );
}
