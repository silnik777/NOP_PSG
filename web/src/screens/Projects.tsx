import { useState } from "react";
import { get, post } from "../api";
import { Card, ErrorBox, useRun } from "../ui";

export default function Projects() {
  const [name, setName] = useState("Gazyfikacja rejonu X mieszanką wodorową");
  const [org, setOrg] = useState("OSD/Strategia");
  const [variantNames, setVariantNames] = useState("Wariant 1 — sprężarka tłokowa; Wariant 2 — większa średnica");
  const [projectId, setProjectId] = useState<number | "">("");

  const create = useRun(async () =>
    post("/api/v1/projects", {
      name, orgUnit: org,
      variants: variantNames.split(";").map((v) => ({ name: v.trim() })).filter((v) => v.name),
    }),
  );
  const load = useRun(async () => get(`/api/v1/projects/${projectId}`));

  const shown = load.data ?? create.data;
  return (
    <>
      <h1>Projekty i warianty</h1>
      <p className="sub">
        Hierarchia biznesowa OPZ: Projekt → Wariant (status SION: Referencyjny / Symulacyjny)
        → niezmienny Wynik (hash SHA-256). Operacje zapisu trafiają do append-only audit logu.
      </p>
      <div className="grid cols-2">
        <Card title="Nowy projekt">
          <div className="form-grid" style={{ gridTemplateColumns: "1fr" }}>
            <label className="f">Nazwa
              <input value={name} onChange={(e) => setName(e.target.value)} />
            </label>
            <label className="f">Jednostka organizacyjna
              <input value={org} onChange={(e) => setOrg(e.target.value)} />
            </label>
            <label className="f">Warianty (rozdzielone średnikiem)
              <input value={variantNames} onChange={(e) => setVariantNames(e.target.value)} />
            </label>
          </div>
          <div className="row mt">
            <button className="primary" disabled={create.busy} onClick={create.run}>Utwórz projekt</button>
          </div>
          <ErrorBox error={create.error} />
        </Card>
        <Card title="Podgląd projektu">
          <div className="row">
            <label className="f" style={{ width: 120 }}>ID projektu
              <input type="number" value={projectId} onChange={(e) => setProjectId(e.target.value === "" ? "" : parseInt(e.target.value, 10))} />
            </label>
            <button className="primary" disabled={load.busy || projectId === ""} onClick={load.run}>Wczytaj</button>
          </div>
          <ErrorBox error={load.error} />
          {shown && (
            <div className="mt">
              <p className="mono" style={{ margin: "0 0 8px" }}>#{shown.id} — {shown.name} <span className="muted">({shown.orgUnit || "brak jednostki"})</span></p>
              <table>
                <thead><tr><th>Wariant</th><th>Status SION</th></tr></thead>
                <tbody>
                  {shown.variants.map((v: any) => (
                    <tr key={v.id}>
                      <td>{v.name}</td>
                      <td>
                        <span className={`badge ${v.status === "Reference" ? "eng" : "scr"}`}>
                          {v.status === "Reference" ? "Referencyjny" : "Symulacyjny"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
