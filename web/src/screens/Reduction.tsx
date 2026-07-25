import { useState } from "react";
import { post } from "../api";
import { Card, ClassBadge, ErrorBox, KV, LineChart, Num, useRun, Warnings } from "../ui";
import { ProfilePicker, useProfiles } from "./common";

export default function Reduction() {
  const profiles = useProfiles();
  const [profile, setProfile] = useState("REF-GAS-E");
  const [mdot, setMdot] = useState(20);
  const [pIn, setPIn] = useState(5);
  const [tIn, setTIn] = useState(288.15);
  const [pOut, setPOut] = useState(1);

  const calc = useRun(async () =>
    post("/api/v1/reduction/station", {
      compositionId: profile,
      massFlowRate: { value: mdot, unit: "kg/s" },
      inletPressure: { value: pIn, unit: "MPa" },
      inletTemperature: { value: tIn, unit: "K" },
      outletPressureTarget: { value: pOut, unit: "MPa" },
    }),
  );

  const d = calc.data;
  const path = d?.ptPath ?? [];
  return (
    <>
      <h1>Moduł III — Stacja redukcyjna</h1>
      <p className="sub">
        Dławienie izentalpowe (efekt Joule'a-Thomsona) z doborem podgrzewu vs turboekspander
        z odzyskiem mocy. Ścieżka p-T na tle krzywej rosy mieszaniny.
      </p>
      <Card title="Parametry stacji">
        <div className="form-grid">
          <ProfilePicker value={profile} onChange={setProfile} profiles={profiles} />
          <Num label="Przepływ [kg/s]" value={mdot} onChange={setMdot} />
          <Num label="p wlot [MPa]" value={pIn} onChange={setPIn} />
          <Num label="T wlot [K]" value={tIn} onChange={setTIn} />
          <Num label="p wylot [MPa]" value={pOut} onChange={setPOut} />
        </div>
        <div className="row mt">
          <button className="primary" disabled={calc.busy} onClick={calc.run}>Analizuj stację</button>
          {d && <ClassBadge cls={d.resultClass} />}
        </div>
        <ErrorBox error={calc.error} />
      </Card>
      {d && (
        <>
          <div className="grid cols-2 mt">
            <Card title="Wariant A — zawór dławiący">
              <KV
                items={[
                  ["T wylotu", d.throttle.outletTemperature.value, "K"],
                  ["Spadek temperatury", d.throttle.temperatureDrop.value, "K"],
                  ["Podgrzew wymagany", d.throttle.preheatRequired ? "TAK" : "NIE"],
                  ...(d.throttle.preheaterDuty
                    ? [
                        ["Moc podgrzewacza", d.throttle.preheaterDuty.value, "kW"],
                        ["T wlotu po podgrzewie", d.throttle.preheatInletTemperature.value, "K"],
                      ] as [string, number, string][]
                    : []),
                ]}
              />
            </Card>
            <Card title="Wariant B — turboekspander">
              <KV
                items={[
                  ["Odzysk mocy", d.expander.recoveredPower.value, "kW"],
                  ["T wylotu (bez podgrzewu)", d.expander.outletTemperature.value, "K"],
                  ["Podgrzew wymagany", d.expander.preheatRequired ? "TAK" : "NIE"],
                  ...(d.expander.preheaterDuty
                    ? ([["Moc podgrzewacza", d.expander.preheaterDuty.value, "kW"]] as [string, number, string][])
                    : []),
                ]}
              />
              {d.expander.netEnergyNote && <div className="warn">{d.expander.netEnergyNote}</div>}
            </Card>
          </div>
          <Card title="Ścieżka p-T dławienia vs krzywa rosy">
            <LineChart
              xLabels={path.map((p: any) => p.pressure.toFixed(2))}
              unit="K (oś X: MPa)"
              series={[
                { name: "Temperatura gazu", values: path.map((p: any) => p.temperature), color: "#4c9be8" },
                { name: "Linia rosy", values: path.map((p: any) => p.dewTemperature), color: "#e06a6a" },
              ]}
            />
            {!d.phaseEnvelopeAvailable && (
              <div className="warn">Obwiednia fazowa niedostępna — margines nieznany.</div>
            )}
            <Warnings list={d.warnings} />
          </Card>
        </>
      )}
    </>
  );
}
