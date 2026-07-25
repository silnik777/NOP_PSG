import { useEffect, useRef, useState } from "react";
import { fmt, post } from "../api";
import { Card, ErrorBox } from "../ui";

interface VariantRow {
  name: string; npv: number; capex: number; co2eTonnes: number; trl: number;
  discountRate: number; scenarioCode: string;
}

const DEFAULT_VARIANTS: VariantRow[] = [
  { name: "W1 — Sprężarka tłokowa", npv: 12_000_000, capex: 18_000_000, co2eTonnes: 9_000, trl: 9, discountRate: 0.06, scenarioCode: "MACRO-ARE-BASE" },
  { name: "W2 — Zwiększenie średnicy", npv: 9_500_000, capex: 14_000_000, co2eTonnes: 4_500, trl: 9, discountRate: 0.06, scenarioCode: "MACRO-ARE-BASE" },
  { name: "W3 — Turboekspander + H₂", npv: 8_000_000, capex: 11_000_000, co2eTonnes: 1_200, trl: 7, discountRate: 0.06, scenarioCode: "MACRO-ARE-BASE" },
];

const CRITERIA = [
  ["npv", "NPV ↑"], ["capex", "CAPEX ↓"], ["co2e", "CO₂e ↓"], ["trl", "TRL ↑"],
] as const;

export default function Mcda() {
  const [variants, setVariants] = useState<VariantRow[]>(DEFAULT_VARIANTS);
  const [weights, setWeights] = useState<Record<string, number>>({ npv: 40, capex: 20, co2e: 25, trl: 15 });
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<unknown>(null);
  const timer = useRef<number | null>(null);

  const total = Object.values(weights).reduce((a, b) => a + b, 0);

  // W7.4 — live re-ranking on weight change (debounced).
  useEffect(() => {
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(async () => {
      try {
        setError(null);
        const res = await post("/api/v1/mcda/rank", {
          variants: variants.map((v) => ({
            name: v.name, npv: v.npv, capex: v.capex, co2eTonnes: v.co2eTonnes, trl: v.trl,
            assumptions: {
              discountRate: v.discountRate, scenarioCode: v.scenarioCode,
              engineVersion: "gpe-core-1.0.0-heos",
            },
          })),
          weights: { npv: weights.npv, capex: weights.capex, co2e: weights.co2e, trl: weights.trl },
        });
        setResult(res);
      } catch (e) {
        setError(e);
        setResult(null);
      }
    }, 250);
    return () => { if (timer.current) window.clearTimeout(timer.current); };
  }, [variants, weights]);

  const edit = (i: number, key: keyof VariantRow, value: number | string) =>
    setVariants((vs) => vs.map((v, j) => (j === i ? { ...v, [key]: value } : v)));

  return (
    <>
      <h1>Panel decyzyjny — MCDA (TOPSIS)</h1>
      <p className="sub">
        Ranking wariantów wg NPV↑ / CAPEX↓ / CO₂e↓ / TRL↑. Wagi normalizują się do 100%,
        zmiana suwaka przelicza ranking na żywo (W7.4). Gatekeeper blokuje porównania przy
        niezgodnych założeniach makro (W7.1/W7.2).
      </p>
      <div className="grid cols-2">
        <Card title="Warianty (kryteria + założenia makro)">
          <table>
            <thead>
              <tr><th>Wariant</th><th>NPV [PLN]</th><th>CAPEX [PLN]</th><th>CO₂e [t]</th><th>TRL</th><th>r</th></tr>
            </thead>
            <tbody>
              {variants.map((v, i) => (
                <tr key={i}>
                  <td>{v.name}</td>
                  {(["npv", "capex", "co2eTonnes", "trl", "discountRate"] as const).map((key) => (
                    <td key={key}>
                      <input
                        style={{ width: key === "discountRate" ? 70 : 110, padding: "3px 6px", fontSize: 12 }}
                        type="number"
                        step="any"
                        value={v[key] as number}
                        onChange={(e) => edit(i, key, parseFloat(e.target.value))}
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted mt">
            Zmień stopę dyskontową jednego wariantu (np. 0.08), by zobaczyć blokadę Gatekeepera.
          </p>
        </Card>
        <Card title={`Wagi kryteriów (suma ${fmt(total, 0)} → normalizowane do 100%)`}>
          {CRITERIA.map(([key, label]) => (
            <div className="slider-row" key={key} style={{ margin: "10px 0" }}>
              <span className="muted">{label}</span>
              <input
                type="range" min={0} max={100} value={weights[key]}
                onChange={(e) => setWeights((w) => ({ ...w, [key]: parseInt(e.target.value, 10) }))}
              />
              <output>{((weights[key] / (total || 1)) * 100).toFixed(0)}%</output>
            </div>
          ))}
          <ErrorBox error={error} />
          {result && (
            <table className="mt">
              <thead><tr><th>Ranking</th><th>Wariant</th><th>Bliskość TOPSIS</th></tr></thead>
              <tbody>
                {result.ranking.map((r: any) => (
                  <tr key={r.name}>
                    <td style={{ fontWeight: 700, color: r.rank === 1 ? "var(--green)" : undefined }}>#{r.rank}</td>
                    <td>{r.name}</td>
                    <td>
                      <div className="row">
                        <div style={{ flex: 1, height: 8, background: "#0c1219", borderRadius: 4 }}>
                          <div style={{ width: `${r.closeness * 100}%`, height: 8, borderRadius: 4, background: "var(--power)" }} />
                        </div>
                        <span className="mono">{fmt(r.closeness, 3)}</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>
    </>
  );
}
