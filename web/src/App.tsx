import { useState } from "react";
import Blend from "./screens/Blend";
import Compression from "./screens/Compression";
import Dashboard from "./screens/Dashboard";
import Finance from "./screens/Finance";
import GasEngine from "./screens/GasEngine";
import Hydraulics from "./screens/Hydraulics";
import Mcda from "./screens/Mcda";
import Outflow from "./screens/Outflow";
import Projects from "./screens/Projects";
import Reduction from "./screens/Reduction";

const SCREENS: [string, string, () => JSX.Element, string][] = [
  ["dashboard", "Ceny i scenariusze", Dashboard, "Analizy"],
  ["finance", "Ekonomika (DCF)", Finance, "Analizy"],
  ["mcda", "Panel decyzyjny (MCDA)", Mcda, "Analizy"],
  ["gas", "Silnik gazowy", GasEngine, "Gaz"],
  ["blend", "Blendowanie i jakość", Blend, "Gaz"],
  ["compression", "Moduł I — Sprężanie", Compression, "Moduły procesowe"],
  ["hydraulics", "Moduł II — Hydraulika", Hydraulics, "Moduły procesowe"],
  ["reduction", "Moduł III — Redukcja", Reduction, "Moduły procesowe"],
  ["outflow", "Moduł IV — Wypływ awaryjny", Outflow, "Moduły procesowe"],
  ["projects", "Projekty i warianty", Projects, "Zarządzanie"],
];

export default function App() {
  const [active, setActive] = useState("dashboard");
  const Screen = SCREENS.find(([id]) => id === active)?.[2] ?? Dashboard;
  const groups = [...new Set(SCREENS.map(([, , , g]) => g))];
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          e-GSD
          <small>Platforma decyzyjna OSD</small>
        </div>
        <nav className="nav" aria-label="Moduły">
          {groups.map((g) => (
            <div key={g}>
              <div className="nav-group">{g}</div>
              {SCREENS.filter(([, , , grp]) => grp === g).map(([id, label]) => (
                <button
                  key={id}
                  className={active === id ? "active" : ""}
                  onClick={() => setActive(id)}
                >
                  {label}
                </button>
              ))}
            </div>
          ))}
        </nav>
      </aside>
      <main className="main">
        <Screen />
      </main>
    </div>
  );
}
