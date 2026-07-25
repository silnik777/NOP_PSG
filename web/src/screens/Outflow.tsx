import { useState } from "react";
import { post } from "../api";
import { Card, ClassBadge, ErrorBox, KV, LineChart, Num, useRun, Warnings } from "../ui";
import { ProfilePicker, useProfiles } from "./common";

export default function Outflow() {
  const profiles = useProfiles();
  const [profile, setProfile] = useState("REF-GAS-H2-20");
  const [p0, setP0] = useState(5);
  const [t, setT] = useState(283.15);
  const [hole, setHole] = useState(100);
  const [pd, setPd] = useState(0.5);
  const [pl, setPl] = useState(10);

  const calc = useRun(async () =>
    post("/api/v1/outflow/blowdown", {
      compositionId: profile,
      initialPressure: { value: p0, unit: "MPa" },
      gasTemperature: { value: t, unit: "K" },
      orificeDiameter: { value: hole, unit: "mm" },
      pipeDiameter: { value: pd, unit: "m" },
      pipeLength: { value: pl, unit: "km" },
    }),
  );

  const d = calc.data;
  const prof = d?.profile ?? [];
  return (
    <>
      <h1>Moduł IV — Awaryjny wypływ (blowdown)</h1>
      <p className="sub">
        Wypływ krytyczny (dławiony) i podkrytyczny przez otwór + dynamiczne opróżnianie odcinka
        (metoda odcinków skupionych). KPI: masa CH₄/H₂, czas do ciśnienia atmosferycznego, Scope 1 CO₂e.
      </p>
      <Card title="Scenariusz rozszczelnienia">
        <div className="form-grid">
          <ProfilePicker value={profile} onChange={setProfile} profiles={profiles} />
          <Num label="p początkowe [MPa]" value={p0} onChange={setP0} />
          <Num label="T gazu [K]" value={t} onChange={setT} />
          <Num label="Otwór (równoważny) [mm]" value={hole} onChange={setHole} />
          <Num label="Średnica rury [m]" value={pd} onChange={setPd} step={0.05} />
          <Num label="Długość odcinka [km]" value={pl} onChange={setPl} />
        </div>
        <div className="row mt">
          <button className="primary" disabled={calc.busy} onClick={calc.run}>Symuluj wypływ</button>
          {d && <ClassBadge cls={d.resultClass} />}
        </div>
        <ErrorBox error={calc.error} />
      </Card>
      {d && (
        <>
          <div className="grid cols-2 mt">
            <Card title="Bilans wypływu">
              <KV
                items={[
                  ["Zapas początkowy", d.initialInventory.value, "t"],
                  ["Wypuszczono łącznie", d.totalReleased.value, "t"],
                  ["w tym CH₄", d.methaneReleased.value, "t"],
                  ["w tym H₂", d.hydrogenReleased.value, "t"],
                  ["Pozostało", d.residualInventory.value, "t"],
                  ["Czas do atmosfery", d.timeToAtmospheric?.value ?? null, "min"],
                  ["Szczytowy strumień", d.peakMassFlow.value, "kg/s"],
                ]}
              />
            </Card>
            <Card title="Ślad emisyjny zdarzenia (Scope 1, AR6)">
              <KV items={[["Emisja CO₂e", d.co2eScope1.value, "t CO₂e"]]} />
              <p className="muted">GWP₁₀₀: CH₄ = 29,8 · H₂ = 11 (IPCC AR6) — liczone w CoreEmissionEngine.</p>
            </Card>
          </div>
          <Card title="Profil ciśnienia i strumienia">
            <LineChart
              xLabels={prof.map((p: any) => p.timeMin.toFixed(0))}
              unit="oś X: minuty"
              series={[
                { name: "Ciśnienie [MPa]", values: prof.map((p: any) => p.pressure), color: "#4c9be8" },
                { name: "Strumień [kg/s]", values: prof.map((p: any) => p.massFlow), color: "#e8a33d" },
              ]}
            />
            <Warnings list={d.warnings} />
          </Card>
        </>
      )}
    </>
  );
}
