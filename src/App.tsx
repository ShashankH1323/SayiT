// App shell: frameless window chrome + left nav + routed screen. Onboarding
// steps take over the whole window (no frame/sidebar). Presentational only —
// all state/actions come from useApp(); screens own their own content.
import { Home, Clock, Settings, Info } from "lucide-react";
import { useApp } from "./lib/appContext";
import { WindowFrame } from "./components/primitives/WindowFrame";
import { SoftBlobBackground } from "./components/primitives/SoftBlobBackground";
import { SidebarItem } from "./components/primitives/SidebarItem";
import { SayItWordmark } from "./components/primitives/SayItWordmark";

import { Splash } from "./components/onboarding/Splash";
import { Welcome } from "./components/onboarding/Welcome";
import { Permissions } from "./components/onboarding/Permissions";
import { Ready } from "./components/onboarding/Ready";

import { Home as HomeScreen } from "./components/app/Home";
import { History } from "./components/app/History";
import { SettingsGeneral } from "./components/app/SettingsGeneral";
import { SettingsAudio } from "./components/app/SettingsAudio";
import { About } from "./components/app/About";

export default function App() {
  const { route, onboarding, actions } = useApp();

  // Onboarding owns the full window — no chrome, no sidebar.
  if (onboarding !== null) {
    switch (onboarding) {
      case "splash":
        return <Splash />;
      case "welcome":
        return <Welcome />;
      case "permissions":
        return <Permissions />;
      case "ready":
        return <Ready />;
    }
  }

  return (
    <div className="flex h-full flex-col">
      <WindowFrame onMinimize={actions.minimize} onClose={actions.close} />

      <div className="flex min-h-0 flex-1">
        <aside className="no-drag flex w-[190px] shrink-0 flex-col gap-1 border-r border-hairline bg-canvas-soft px-3 py-4">
          <div className="px-2 pb-4 pt-1">
            <SayItWordmark size="sm" withMark />
          </div>
          <nav className="flex flex-col gap-1">
            <SidebarItem
              icon={<Home />}
              label="Home"
              active={route === "home"}
              onClick={() => actions.navigate("home")}
            />
            <SidebarItem
              icon={<Clock />}
              label="History"
              active={route === "history"}
              onClick={() => actions.navigate("history")}
            />
            <SidebarItem
              icon={<Settings />}
              label="Settings"
              active={route.startsWith("settings")}
              onClick={() => actions.navigate("settings-general")}
            />
            <SidebarItem
              icon={<Info />}
              label="About"
              active={route === "about"}
              onClick={() => actions.navigate("about")}
            />
          </nav>
        </aside>

        <main className="relative min-h-0 flex-1 overflow-y-auto">
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
    case "settings-general":
      return <SettingsGeneral />;
    case "settings-audio":
      return <SettingsAudio />;
    case "about":
      return <About />;
  }
}
