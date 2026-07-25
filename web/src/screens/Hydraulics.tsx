import { useState } from "react";
import { post } from "../api";
import { Card, ClassBadge, ErrorBox, KV, Num, useRun, Warnings } from "../ui";
import { ProfilePicker, useProfiles } from "./common";

export default function Hydraulics() {
  const profiles = useProfiles();
  const [profile, setProfile] = useState("REF-GAS-E");
  const [d, setD] = useState(0.5);
  const [k, setK] = useState(0.012);
  const [len, setLen] = useState(50);
  const [pIn, setPIn] = useState(5);
  const [t, setT] = useState(283.15);
  const [flow, setFlow] = useState(100000);

  const body = () => ({
    compositionId: profile,
    diameter: { value: d, unit: "m" },
    roughness: { value: k, unit: "mm" },
    length: { value: len, unit: "km" },
    inletPressure: { value: pIn, unit: "MPa" },
    gasTemperature: { value: t, unit: "K" },
    normalFlow: { value: flow, unit: "Nm3/h" },
  });

  const steady = useRun(async () => post("/api/v1/hydraulics/steady-flow", body()));
  const linepack = useRun(async () => post("/api/v1/hydraulics/linepack", body()));

  return (
    <>
      <h1>Moduł II — Hydraulika i linepack</h1>
      <p className="sub">
        Przepływ ustalony izotermiczny (Colebrook-White + ogólne równanie gazu ściśliwego,
        iteracja po Z). Baza odniesienia: warunki normalne 0 °C / 101,325 kPa (Nm³).
      </p>
      <Card title="Geometria i warunki">
        <div className="form-grid">
          <ProfilePicker value={profile} onChange={setProfile} profiles={profiles} />
          <Num label="Średnica wewn. D [m]" value={d} onChange={setD} step={0.05} />
          <Num label="Chropowatość k [mm]" value={k} onChange={setK} step={0.001} />
          <Num label="Długość L [km]" value={len} onChange={setLen} />
          <Num label="p wlot [MPa]" value={pIn} onChange={setPIn} />
          <Num label="T gazu [K]" value={t} onChange={setT} />
          <Num label="Przepływ [Nm³/h]" value={flow} onChange={setFlow} />
        </div>
        <div className="row mt">
          <button className="primary" disabled={steady.busy} onClick={steady.run}>Przepływ ustalony</button>
          <button className="primary" disabled={linepack.busy} onClick={linepack.run}>Linepack</button>
          <a
            className="muted"
            href="#"
            onClick={async (e) => {
              e.preventDefault();
              const res = await fetch("/api/v1/export/hydraulics?format=xlsx", {
                method: "POST",
                headers: { "content-type": "application/json" },
                body: JSON.stringify(body()),
              });
              const blob = await res.blob();
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url; a.download = "hydraulics.xlsx"; a.click();
              URL.revokeObjectURL(url);
            }}
          >
            Eksport XLSX ↓
          </a>
        </div>
        <ErrorBox error={steady.error ?? linepack.error} />
      </Card>
      <div className="grid cols-2 mt">
        {steady.data && (
          <Card title="Wynik hydrauliczny" right={<ClassBadge cls={steady.data.resultClass} />}>
            <KV
              items={[
                ["Ciśnienie wylotowe", steady.data.outletPressure.value, "MPa"],
                ["Spadek ciśnienia", steady.data.pressureDrop.value * 1000, "kPa"],
                ["Przepływ masowy", steady.data.massFlow.value, "kg/s"],
                ["Prędkość średnia", steady.data.averageVelocity.value, "m/s"],
                ["Liczba Reynoldsa", steady.data.reynoldsNumber],
                ["λ (Darcy)", steady.data.frictionFactor],
                ["Reżim", steady.data.flowRegime],
                ["Mach", steady.data.machNumber],
              ]}
            />
            <Warnings list={steady.data.warnings} />
          </Card>
        )}
        {linepack.data && (
          <Card title="Linepack (pojemność akumulacyjna)">
            <KV
              items={[
                ["Masa zmagazynowana", linepack.data.linepackMass.value, "t"],
                ["Objętość normalna", linepack.data.linepackNormalVolume.value, "Nm³"],
                ["Ciśnienie średnie", linepack.data.averagePressure.value, "MPa"],
                ["Gęstość średnia", linepack.data.averageDensity.value, "kg/m³"],
              ]}
            />
          </Card>
        )}
      </div>
    </>
  );
}
