import { useState } from "react";
import { fmt, post } from "../api";
import { Card, ErrorBox, KV, Num, useRun } from "../ui";
import { ProfilePicker, useProfiles } from "./common";

export default function Blend() {
  const profiles = useProfiles();
  const [grid, setGrid] = useState(70);
  const [h2, setH2] = useState(20);
  const [sng, setSng] = useState(10);
  const [gridCode, setGridCode] = useState("REF-GAS-E");

  const blend = useRun(async () =>
    post("/api/v1/gas/blend", {
      streams: [
        { compositionId: gridCode, share: grid },
        { compositionId: "REF-STREAM-H2-ELX", share: h2 },
        { compositionId: "REF-STREAM-SNG", share: sng },
      ],
    }),
  );

  const quality = useRun(async () => {
    if (!blend.data) throw new Error("Najpierw policz blend.");
    return post("/api/v1/gas/quality-check", { gasComposition: blend.data.composition });
  });

  const prop = quality.data?.proposal;
  return (
    <>
      <h1>Blendowanie i jakość gazu</h1>
      <p className="sub">
        Własna kompozycja z udziałów procentowych: gaz sieciowy + wodór z elektrolizy + SNG z metanizacji.
        Kontrola vs standard gazu wysokometanowego (grupa E) z propozycją propanizacji.
      </p>
      <div className="grid cols-2">
        <Card title="Strumienie blendu (udziały molowe)">
          <div className="form-grid">
            <ProfilePicker value={gridCode} onChange={setGridCode} profiles={profiles} label="Gaz sieciowy" />
            <Num label="Udział sieciowy [%]" value={grid} onChange={setGrid} />
            <Num label="H₂ z elektrolizy [%]" value={h2} onChange={setH2} />
            <Num label="SNG z metanizacji [%]" value={sng} onChange={setSng} />
          </div>
          <div className="row mt">
            <button className="primary" disabled={blend.busy} onClick={blend.run}>Zblenduj</button>
          </div>
          <ErrorBox error={blend.error} />
          {blend.data && (
            <div className="mt">
              <KV
                items={[
                  ["HHV", blend.data.grossCalorificValue.value, "MJ/m³"],
                  ["Liczba Wobbego", blend.data.wobbeIndex.value, "MJ/m³"],
                  ["Gęstość względna", blend.data.relativeDensity, "—"],
                  ["Gęstość normalna", blend.data.normalDensity.value, "kg/m³"],
                ]}
              />
              <table className="mt">
                <thead><tr><th>Składnik</th><th>Ułamek molowy</th></tr></thead>
                <tbody>
                  {Object.entries(blend.data.composition as Record<string, number>)
                    .sort(([, a], [, b]) => b - a)
                    .map(([k, v]) => (
                      <tr key={k}><td>{k}</td><td>{fmt(v, 4)}</td></tr>
                    ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
        <Card title="Kontrola jakości (grupa E)">
          <div className="row">
            <button className="primary" disabled={quality.busy || !blend.data} onClick={quality.run}>
              Sprawdź jakość
            </button>
            {quality.data && (
              <span className={`badge ${quality.data.withinSpec ? "eng" : "err"}`}>
                {quality.data.withinSpec ? "W normie" : "Poza normą"}
              </span>
            )}
          </div>
          <ErrorBox error={quality.error} />
          {quality.data && (
            <div className="mt">
              <KV
                items={[
                  ["Wobbe", quality.data.wobbeIndex.value, "MJ/m³"],
                  ["HHV", quality.data.grossCalorificValue.value, "MJ/m³"],
                ]}
              />
              {quality.data.violations.map((v: string, i: number) => (
                <div className="warn" key={i}>{v}</div>
              ))}
              {prop && (
                <div className="card mt" style={{ borderColor: "#56421c" }}>
                  <h2 style={{ color: "var(--amber)" }}>
                    Propozycja: {prop.action === "propanization" ? "propanizacja" : "balastowanie N₂"}
                  </h2>
                  <KV
                    items={[
                      [`Dodatek (${prop.additive})`, prop.additiveFractionMol * 100, "% mol"],
                      ["Wobbe po korekcie", prop.resultingWobbe.value, "MJ/m³"],
                      ["HHV po korekcie", prop.resultingGrossCv.value, "MJ/m³"],
                    ]}
                  />
                  <p className="muted" style={{ marginBottom: 0 }}>{prop.note}</p>
                </div>
              )}
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
