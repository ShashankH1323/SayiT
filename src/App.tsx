// App shell: frameless window chrome + left nav + routed screen. Onboarding
// steps take over the whole window (no frame/sidebar). Presentational only —
// all state/actions come from useApp(); screens own their own content.
import { useState } from "react";
import { Home, Clock, Sparkles, Settings, Info, PanelLeftClose, PanelLeft } from "lucide-react";
import { useApp } from "./lib/appContext";
import { WindowFrame } from "./components/primitives/WindowFrame";
import { SoftBlobBackground } from "./components/primitives/SoftBlobBackground";
import { SidebarItem } from "./components/primitives/SidebarItem";
import { SayItWordmark } from "./components/primitives/SayItWordmark";
import { SayItMark } from "./components/primitives/SayItMark";
import { cn } from "./lib/utils";

import { Splash } from "./components/onboarding/Splash";
import { Welcome } from "./components/onboarding/Welcome";
import { Permissions } from "./components/onboarding/Permissions";
import { HotkeyGuide } from "./components/onboarding/HotkeyGuide";
import { Ready } from "./components/onboarding/Ready";

import { Home as HomeScreen } from "./components/app/Home";
import { History } from "./components/app/History";
import { Transcription } from "./components/app/Transcription";
import { SettingsGeneral } from "./components/app/SettingsGeneral";
import { SettingsAudio } from "./components/app/SettingsAudio";
import { About } from "./components/app/About";

export default function App() {
  const { route, onboarding, actions } = useApp();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // Onboarding owns the full window with frameless drag support.
  if (onboarding !== null) {
    const handleDrag = (e: React.MouseEvent) => {
      if (e.button === 0 && !(e.target as HTMLElement).closest("button, input, select, a, .no-drag")) {
        actions.windowDrag();
      }
    };

    return (
      <div onMouseDown={handleDrag} className="h-full w-full select-none overflow-x-hidden">
        {onboarding === "splash" && <Splash />}
        {onboarding === "welcome" && <Welcome />}
        {onboarding === "permissions" && <Permissions />}
        {onboarding === "hotkey" && <HotkeyGuide />}
        {onboarding === "ready" && <Ready />}
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-x-hidden">
      <WindowFrame onMinimize={actions.minimize} onClose={actions.close} />

      <div className="flex min-h-0 flex-1 overflow-x-hidden">
        <aside
          className={cn(
            "no-drag flex shrink-0 flex-col gap-1 border-r border-hairline bg-canvas-soft transition-all duration-200 ease-in-out py-4",
            sidebarCollapsed ? "w-[64px] px-2" : "w-[190px] px-3",
          )}
        >
          {/* Sidebar Top: Logo + Collapse/Expand Toggle */}
          <div
            className={cn(
              "flex items-center pb-3 pt-1",
              sidebarCollapsed ? "flex-col gap-2 justify-center" : "justify-between px-2",
            )}
          >
            {sidebarCollapsed ? (
              <div className="grid h-8 w-8 place-items-center">
                <SayItMark size={22} />
              </div>
            ) : (
              <SayItWordmark size="sm" withMark />
            )}
            <button
              type="button"
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
              title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
              aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
              className="grid h-7 w-7 place-items-center rounded-md text-ink-tertiary hover:bg-black/[.04] hover:text-ink transition-colors"
            >
              {sidebarCollapsed ? <PanelLeft className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
            </button>
          </div>

          <nav className="flex flex-col gap-1">
            <SidebarItem
              icon={<Home />}
              label="Home"
              active={route === "home"}
              collapsed={sidebarCollapsed}
              onClick={() => actions.navigate("home")}
            />
            <SidebarItem
              icon={<Clock />}
              label="History"
              active={route === "history"}
              collapsed={sidebarCollapsed}
              onClick={() => actions.navigate("history")}
            />
            <SidebarItem
              icon={<Sparkles />}
              label="Transcription"
              active={route === "transcription"}
              collapsed={sidebarCollapsed}
              onClick={() => actions.navigate("transcription")}
            />
            <SidebarItem
              icon={<Settings />}
              label="Settings"
              active={route.startsWith("settings")}
              collapsed={sidebarCollapsed}
              onClick={() => actions.navigate("settings-general")}
            />
            <SidebarItem
              icon={<Info />}
              label="About"
              active={route === "about"}
              collapsed={sidebarCollapsed}
              onClick={() => actions.navigate("about")}
            />
          </nav>
        </aside>

        <main className="relative min-h-0 flex-1 overflow-y-auto overflow-x-hidden">
          <SoftBlobBackground variant="subtle" />
          {renderScreen(route)}
        </main>
      </div>
    </div>
  );
}

function renderScreen(route: ReturnType<typeof useApp>["route"]) {
  switch (route) {
    case "home":
      return <HomeScreen />;
    case "history":
      return <History />;
    case "transcription":
      return <Transcription />;
    case "settings-general":
      return <SettingsGeneral />;
    case "settings-audio":
      return <SettingsAudio />;
    case "about":
      return <About />;
  }
}
