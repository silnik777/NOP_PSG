import { useState } from "react";
import { fmt, post } from "../api";
import { Card, ErrorBox, KV, Num, Sel, useRun, Warnings } from "../ui";

export default function Finance() {
  const [capex, setCapex] = useState(15_000_000);
  const [rate, setRate] = useState(0.08);
  const [years, setYears] = useState(10);
  const [opex, setOpex] = useState(300_000);
  const [revenue, setRevenue] = useState(5_000_000);
  const [output, setOutput] = useState(20_000);
  const [lco, setLco] = useState("LCOE");

  const body = () => ({
    capex,
    discountRate: rate,
    horizonYears: years,
    opexPerYear: Array(years).fill(opex),
    revenuePerYear: Array(years).fill(revenue),
    outputPerYear: Array(years).fill(output),
    lcoKind: lco,
  });

  const dcf = useRun(async () => post("/api/v1/finance/dcf", body()));
  const tornado = useRun(async () => post("/api/v1/finance/sensitivity", body()));

  const axes = tornado.data?.axes ?? [];
  const baseNpv = tornado.data?.baseNpv ?? 0;
  const spans = axes
    .map((a: any) => {
      const npvs = a.points.map((p: any) => p.npv);
      return { name: a.parameter, min: Math.min(...npvs), max: Math.max(...npvs) };
    })
    .sort((a: any, b: any) => (b.max - b.min) - (a.max - a.min));
  const lo = Math.min(baseNpv, ...spans.map((s: any) => s.min));
  const hi = Math.max(baseNpv, ...spans.map((s: any) => s.max));
  const scale = (v: number) => ((v - lo) / (hi - lo || 1)) * 100;

  return (
    <>
      <h1>Ekonomika — DCF</h1>
      <p className="sub">
        CoreFinanceEngine: NPV, IRR (Brent z detekcją przepływów niekonwencjonalnych),
        wskaźniki LCO oraz analiza wrażliwości ±30% (wykres tornado, W5.1).
      </p>
      <Card title="Założenia projektu">
        <div className="form-grid">
          <Num label="CAPEX [PLN]" value={capex} onChange={setCapex} />
          <Num label="Stopa dyskontowa" value={rate} onChange={setRate} step={0.005} />
          <Num label="Horyzont [lata]" value={years} onChange={setYears} />
          <Num label="OPEX / rok [PLN]" value={opex} onChange={setOpex} />
          <Num label="Przychód / rok [PLN]" value={revenue} onChange={setRevenue} />
          <Num label="Produkcja / rok" value={output} onChange={setOutput} />
          <Sel label="Wskaźnik LCO" value={lco} onChange={setLco}
            options={[["LCOE", "LCOE (MWh)"], ["LCOH", "LCOH (kg H₂)"], ["LCOHeat", "LCOHeat (GJ)"], ["LCOS", "LCOS (MWh)"]]} />
        </div>
        <div className="row mt">
          <button className="primary" disabled={dcf.busy} onClick={dcf.run}>Policz DCF</button>
          <button className="primary" disabled={tornado.busy} onClick={tornado.run}>Analiza wrażliwości</button>
        </div>
        <ErrorBox error={dcf.error ?? tornado.error} />
      </Card>
      <div className="grid cols-2 mt">
        {dcf.data && (
          <Card title="Wynik DCF">
            <KV
              items={[
                ["NPV", dcf.data.npv, "PLN"],
                ["IRR", dcf.data.irr !== null ? `${fmt(dcf.data.irr * 100, 2)} %` : "—"],
                [dcf.data.lcoKind ?? "LCO", dcf.data.lcoValue, "PLN/jedn."],
              ]}
            />
            <Warnings list={dcf.data.warnings} />
          </Card>
        )}
        {spans.length > 0 && (
          <Card title={`Tornado NPV (baza ${fmt(baseNpv, 0)} PLN)`}>
            {spans.map((s: any) => (
              <div key={s.name} className="slider-row" style={{ margin: "8px 0" }}>
                <span className="muted">{s.name}</span>
                <div style={{ position: "relative", height: 18, background: "#0c1219", borderRadius: 6 }}>
                  <div
                    style={{
                      position: "absolute", top: 3, height: 12, borderRadius: 4,
                      left: `${scale(s.min)}%`, width: `${Math.max(1, scale(s.max) - scale(s.min))}%`,
                      background: "linear-gradient(90deg,#e06a6a,#5fbf8f)",
                    }}
                  />
                  <div style={{ position: "absolute", top: 0, bottom: 0, width: 2, background: "#e7edf5", left: `${scale(baseNpv)}%` }} />
                </div>
                <output>{fmt((s.max - s.min) / 1e6, 1)}M</output>
              </div>
            ))}
            <p className="muted" style={{ marginBottom: 0 }}>Rozpiętość NPV przy zmianie parametru ±30% (krok 5%).</p>
          </Card>
        )}
      </div>
    </>
  );
}
