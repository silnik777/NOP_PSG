import { useState } from "react";
import { fmt, post } from "../api";
import { Card, ClassBadge, ErrorBox, KV, Num, useRun, Warnings } from "../ui";
import { ProfilePicker, useProfiles } from "./common";

export default function Compression() {
  const profiles = useProfiles();
  const [profile, setProfile] = useState("REF-GAS-H2-20");
  const [mdot, setMdot] = useState(10);
  const [pIn, setPIn] = useState(2);
  const [tIn, setTIn] = useState(288.15);
  const [pOut, setPOut] = useState(5);
  const [eta, setEta] = useState(0.8);

  const base = () => ({
    compositionId: profile,
    massFlowRate: { value: mdot, unit: "kg/s" },
    inletPressure: { value: pIn, unit: "MPa" },
    inletTemperature: { value: tIn, unit: "K" },
    outletPressureTarget: { value: pOut, unit: "MPa" },
  });

  const calc = useRun(async () => post("/api/v1/thermo/compression", { ...base(), isentropicEfficiency: eta }));
  const select = useRun(async () => post("/api/v1/devices/select-compressor", base()));

  return (
    <>
      <h1>Moduł I — Sprężanie</h1>
      <p className="sub">
        Bilans entalpowy ze sprawnością izentropową (GERG-2008) oraz dobór technologii sprężarki
        z katalogu urządzeń wraz z chłodnicami.
      </p>
      <Card title="Parametry">
        <div className="form-grid">
          <ProfilePicker value={profile} onChange={setProfile} profiles={profiles} />
          <Num label="Przepływ masowy [kg/s]" value={mdot} onChange={setMdot} />
          <Num label="p wlot [MPa]" value={pIn} onChange={setPIn} />
          <Num label="T wlot [K]" value={tIn} onChange={setTIn} />
          <Num label="p wylot [MPa]" value={pOut} onChange={setPOut} />
          <Num label="η izentropowa (ręczna)" value={eta} onChange={setEta} step={0.01} />
        </div>
        <div className="row mt">
          <button className="primary" disabled={calc.busy} onClick={calc.run}>Oblicz (η ręczna)</button>
          <button className="primary" disabled={select.busy} onClick={select.run}>Dobierz sprężarkę z bazy</button>
        </div>
        <ErrorBox error={calc.error ?? select.error} />
      </Card>
      <div className="grid cols-2 mt">
        {calc.data && (
          <Card title="Wynik obliczenia" right={<ClassBadge cls={calc.data.resultClass} />}>
            <KV
              items={[
                ["Moc na wale", calc.data.requiredShaftPower.value, "kW"],
                ["Temperatura wylotu", calc.data.outletTemperature.value, "K"],
                ["Spręż rzeczywisty (head)", calc.data.polytropicHead.value, "kJ/kg"],
                ["Spręż izentropowy", calc.data.isentropicHead.value, "kJ/kg"],
                ["Status walidacji", calc.data.validationStatus],
              ]}
            />
            <Warnings list={calc.data.warnings} />
          </Card>
        )}
        {select.data && (
          <Card title="Dobór urządzenia" right={<ClassBadge cls={select.data.resultClass} />}>
            <KV
              items={[
                ["Technologia", `${select.data.selected.name}`],
                ["Stopnie", select.data.selected.stages],
                ["Spręż na stopień", select.data.selected.stageRatio],
                ["η efektywna", select.data.selected.effectiveEfficiency],
                ["Moc na wale", select.data.requiredShaftPower.value, "kW"],
                ["T wylotu", select.data.outletTemperature.value, "K"],
              ]}
            />
            {select.data.auxiliaries.map((a: any, i: number) => (
              <div className="warn" key={i}>
                <b>{a.kind}</b>: {a.description} {a.duty && `(${fmt(a.duty.value, 0)} ${a.duty.unit})`}
              </div>
            ))}
            <table className="mt">
              <thead><tr><th>Alternatywa</th><th>η</th><th>Stopnie</th><th>Status</th></tr></thead>
              <tbody>
                {select.data.alternatives.map((c: any) => (
                  <tr key={c.code}>
                    <td>{c.name}</td>
                    <td>{c.feasible ? fmt(c.effectiveEfficiency, 3) : "—"}</td>
                    <td>{c.feasible ? c.stages : "—"}</td>
                    <td style={{ fontFamily: "var(--sans)", fontSize: 12 }}>
                      {c.feasible ? "wykonalna" : c.reason}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}
      </div>
    </>
  );
}
