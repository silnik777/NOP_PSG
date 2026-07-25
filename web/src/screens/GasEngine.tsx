import { useState } from "react";
import { post } from "../api";
import { Card, ErrorBox, KV, Num, useRun, Warnings } from "../ui";
import { ProfilePicker, useProfiles } from "./common";

export default function GasEngine() {
  const profiles = useProfiles();
  const [profile, setProfile] = useState("REF-GAS-H2-20");
  const [p, setP] = useState(5.5);
  const [t, setT] = useState(285.15);

  const props = useRun(async () => {
    const chosen = profiles.find((x) => x.code === profile);
    return post("/api/v1/gas-engine/point-properties", {
      gasComposition: chosen?.fractions ?? { methane: 0.8, hydrogen: 0.2 },
      stateVariables: {
        pressure: { value: p, unit: "MPa" },
        temperature: { value: t, unit: "K" },
      },
    });
  });
  const comb = useRun(async () => {
    const chosen = profiles.find((x) => x.code === profile);
    return post("/api/v1/gas-engine/combustion", {
      gasComposition: chosen?.fractions ?? { methane: 1.0 },
      referencePair: "25/0",
    });
  });

  const cv = props.data?.calculatedValues;
  return (
    <>
      <h1>Silnik właściwości gazów</h1>
      <p className="sub">GERG-2008 (CoolProp HEOS) — właściwości punktu (p, T) oraz parametry spalania ISO 6976.</p>
      <div className="grid cols-2">
        <Card title="Właściwości termodynamiczne punktu">
          <div className="form-grid">
            <ProfilePicker value={profile} onChange={setProfile} profiles={profiles} />
            <Num label="Ciśnienie [MPa]" value={p} onChange={setP} />
            <Num label="Temperatura [K]" value={t} onChange={setT} />
          </div>
          <div className="row mt">
            <button className="primary" disabled={props.busy} onClick={props.run}>Oblicz</button>
            {props.data && (
              <span className="muted mono">silnik: {props.data.meta.engineVersion}</span>
            )}
          </div>
          <ErrorBox error={props.error} />
          {cv && (
            <div className="mt">
              <KV
                items={[
                  ["Współczynnik ściśliwości Z", cv.compressibilityFactor.value, "—"],
                  ["Gęstość", cv.density.value, cv.density.unit],
                  ["Masa molowa", cv.molarMass.value, cv.molarMass.unit],
                  ["Cp", cv.specificHeatCp.value, cv.specificHeatCp.unit],
                  ["Współczynnik Joule'a-Thomsona", cv.jouleThomsonCoefficient.value, cv.jouleThomsonCoefficient.unit],
                  ["Prędkość dźwięku", cv.speedOfSound.value, cv.speedOfSound.unit],
                ]}
              />
              <Warnings list={props.data.validation.warnings} />
            </div>
          )}
        </Card>
        <Card title="Spalanie (ISO 6976, 25/0 °C)">
          <div className="row">
            <button className="primary" disabled={comb.busy} onClick={comb.run}>Oblicz spalanie</button>
          </div>
          <ErrorBox error={comb.error} />
          {comb.data && (
            <div className="mt">
              <KV
                items={[
                  ["Ciepło spalania (HHV)", comb.data.grossCalorificValue.value, "MJ/m³"],
                  ["Wartość opałowa (LHV)", comb.data.netCalorificValue.value, "MJ/m³"],
                  ["Liczba Wobbego", comb.data.wobbeIndex.value, "MJ/m³"],
                  ["Gęstość względna", comb.data.relativeDensity, "—"],
                ]}
              />
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
