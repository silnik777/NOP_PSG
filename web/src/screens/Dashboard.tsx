import { useEffect, useState } from "react";
import { fmt, get } from "../api";
import { Card, KV } from "../ui";

interface Series {
  code: string; name: string; unit: string; source: string;
  current: { date: string; value: number };
}
interface Band { year: number; low: number; base: number; high: number }

export default function Dashboard() {
  const [series, setSeries] = useState<Series[]>([]);
  const [scenario, setScenario] = useState<{ bands: Band[]; basis: string; referenceValue: number } | null>(null);

  useEffect(() => {
    get<Series[]>("/api/v1/prices").then(setSeries).catch(() => {});
    get("/api/v1/prices/EU_ETS_EUA/report-scenario").then(setScenario).catch(() => {});
  }, []);

  const milestones = scenario?.bands.filter((b) => [2026, 2030, 2035, 2040, 2045, 2050].includes(b.year)) ?? [];

  return (
    <>
      <h1>Ceny rynkowe i scenariusze</h1>
      <p className="sub">
        Ceny aktualne i historia ~6 miesięcy dają poziom odniesienia; trajektorie do 2050
        pochodzą ze scenariuszy raportowych (ARE/PEP2040/KPEiR, Fit-for-55, EU Reference),
        zakotwiczonych do ceny bieżącej.
      </p>
      <div className="grid cols-3">
        {series.map((s) => (
          <Card key={s.code} title={s.name}>
            <KV items={[["Cena bieżąca", s.current.value, s.unit], ["Na dzień", s.current.date]]} />
            <p className="muted" style={{ marginBottom: 0 }}>{s.source}</p>
          </Card>
        ))}
      </div>
      <div className="grid cols-2 mt">
        {series.map((s) => (
          <Card key={s.code} title={`${s.name} — 6 miesięcy`}>
            <img className="chart-img" src={`/api/v1/prices/${s.code}/chart.svg?weeks=26`} alt={`Wykres ${s.name}`} />
          </Card>
        ))}
        {scenario && (
          <Card title={`EU ETS — scenariusz raportowy (kotwica ${fmt(scenario.referenceValue, 1)} EUR/t)`}>
            <table>
              <thead>
                <tr><th>Rok</th><th>Low</th><th>Base</th><th>High</th></tr>
              </thead>
              <tbody>
                {milestones.map((b) => (
                  <tr key={b.year}>
                    <td>{b.year}</td>
                    <td>{fmt(b.low, 0)}</td>
                    <td style={{ color: "var(--green)" }}>{fmt(b.base, 0)}</td>
                    <td>{fmt(b.high, 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="muted mt" style={{ marginBottom: 0 }}>{scenario.basis}</p>
          </Card>
        )}
      </div>
    </>
  );
}
