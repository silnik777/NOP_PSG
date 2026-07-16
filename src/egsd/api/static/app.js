"use strict";
// e-GSD web GUI — vanilla JS SPA consuming the FastAPI backend. No build step, no external
// libraries. All heavy computation stays on the server (OPZ B.3).

const API = "/api/v1";
let authToken = localStorage.getItem("egsd_token") || "";

// ---------- tiny helpers ------------------------------------------------------
const $ = (sel, root = document) => root.querySelector(sel);
const el = (tag, attrs = {}, ...kids) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k === "html") n.innerHTML = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined) n.setAttribute(k, v);
  }
  for (const kid of kids.flat()) {
    if (kid == null) continue;
    n.appendChild(typeof kid === "string" ? document.createTextNode(kid) : kid);
  }
  return n;
};
const fmt = (v) => {
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(4).replace(/\.?0+$/, "");
  if (Array.isArray(v)) return v.map(fmt).join(", ");
  if (v && typeof v === "object") return Object.entries(v).map(([k, x]) => `${k}: ${fmt(x)}`).join("; ");
  return String(v);
};
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg; t.hidden = false;
  clearTimeout(t._h); t._h = setTimeout(() => (t.hidden = true), 5000);
}
async function api(path, { method = "GET", body } = {}) {
  const opt = { method, headers: {} };
  if (authToken) opt.headers["Authorization"] = "Bearer " + authToken;
  if (body !== undefined) { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
  const res = await fetch(API + path, opt);
  const text = await res.text();
  let data; try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (!res.ok) {
    const detail = (data && data.detail) ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : res.statusText;
    const err = new Error(detail); err.status = res.status; throw err;
  }
  return data;
}
const parseJSON = (str, fallback) => { try { return JSON.parse(str); } catch { return fallback; } };

// ---------- rendering primitives ---------------------------------------------
function kvTable(obj) {
  const rows = Object.entries(obj).map(([k, v]) =>
    el("tr", {}, el("th", {}, k), el("td", {}, fmt(v))));
  return el("table", { class: "kv" }, ...rows);
}
function dataTable(columns, rows, textCols = []) {
  const head = el("tr", {}, ...columns.map((c) =>
    el("th", { class: textCols.includes(c) ? "txt" : "" }, c)));
  const body = rows.map((r) => el("tr", {}, ...columns.map((c) =>
    el("td", { class: textCols.includes(c) ? "txt" : "" }, fmt(r[c])))));
  return el("div", { class: "tablewrap" }, el("table", { class: "data" }, el("thead", {}, head), el("tbody", {}, ...body)));
}
function warnBox(warnings) {
  if (!warnings || !warnings.length) return null;
  return el("div", { class: "warnbox" }, el("strong", {}, "Ostrzeżenia / uwagi:"),
    el("ul", {}, ...warnings.map((w) => el("li", {}, w))));
}
function field(label, input) { return el("div", { class: "field" }, el("label", {}, label), input); }
function resultPanel(node) {
  const box = el("div", { class: "result" }, node);
  return box;
}
async function withBusy(btn, fn) {
  const old = btn.innerHTML; btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> licz…';
  try { return await fn(); }
  catch (e) { toast(`Błąd ${e.status || ""}: ${e.message}`); throw e; }
  finally { btn.disabled = false; btn.innerHTML = old; }
}

// ---------- composition editor (reusable) ------------------------------------
const DEFAULT_GAS = { methane: 0.95, ethane: 0.03, propane: 0.02 };
function compositionField(initial = DEFAULT_GAS) {
  const ta = el("textarea", { spellcheck: "false" }, JSON.stringify(initial));
  return { node: field("Skład gazu (JSON: składnik → udział)", ta), get: () => parseJSON(ta.value, null), el: ta };
}

// ---------- screens -----------------------------------------------------------
const screens = {};

// 0. Pulpit ---------------------------------------------------------------------
screens.start = {
  title: "Pulpit", icon: "🏠", step: "Start",
  sub: "Platforma wspomagania decyzji: jeden spójny łańcuch obliczeniowy od składu gazu do wyniku ekonomicznego i rankingu technologii — wersjonowany i odtwarzalny (OPZ).",
  async render(root) {
    const panel = el("div", { class: "panel" }, el("h2", {}, "Łańcuch analizy (OPZ)"),
      el("p", { class: "muted" }, "Przechodź kolejno przez moduły w menu po lewej. Każdy wynik niesie klasę jakości i metadane; wyniki historyczne są niezmienne."));
    const chain = ["Profile i mieszaniny", "Jakość i propan", "Spalanie i emisje", "Technologie ekspansji",
      "Ekonomika (DCF)", "Merit order", "Ceny i prognozy", "Raport techniczny"];
    panel.appendChild(el("div", { class: "rowline" }, ...chain.map((c, i) =>
      el("span", { class: "pill" }, `${i + 1}. ${c}`))));
    root.appendChild(panel);

    const status = el("div", { class: "panel" }, el("h2", {}, "Stan systemu"), el("div", {}, "…"));
    root.appendChild(status);
    try {
      const h = await fetch("/health").then((r) => r.json());
      const who = await api("/auth/whoami");
      status.lastChild.replaceWith(kvTable({
        "Status": h.status, "Wersja silnika gazowego": h.engineVersion,
        "Uwierzytelnianie": who.authEnabled ? "włączone" : "wyłączone (tryb dev)",
        "Rola bieżąca": who.role,
      }));
    } catch (e) { status.lastChild.replaceWith(el("div", { class: "muted" }, "Nie udało się pobrać stanu: " + e.message)); }
  },
};

// 1. Profile i mieszaniny -------------------------------------------------------
screens.profiles = {
  title: "Profile i mieszaniny", icon: "🧪", step: "Gaz",
  sub: "Twórz własne, wersjonowane profile składu gazu i mieszaj strumienie (własny + bazowy). Zapisany profil jest używalny wszędzie jako identyfikator kompozycji.",
  async render(root) {
    // --- create profile ---
    const p1 = el("div", { class: "panel" }, el("h2", {}, "Nowy profil składu"));
    const name = el("input", { value: "Mój gaz" });
    const comp = compositionField({ methane: 0.62, carbon_dioxide: 0.36, nitrogen: 0.02 });
    const status = el("select", {}, ...["draft", "user", "approved"].map((s) => el("option", {}, s)));
    p1.append(el("div", { class: "grid" }, field("Nazwa", name), field("Status", status)), comp.node);
    const out1 = el("div", {});
    const save = el("button", { class: "btn" }, "Zapisz profil");
    save.addEventListener("click", () => withBusy(save, async () => {
      const g = comp.get(); if (!g) return toast("Nieprawidłowy JSON składu.");
      const r = await api("/gas/profiles", { method: "POST", body: { name: name.value, gasComposition: g, status: status.value } });
      out1.replaceChildren(resultPanel(el("div", {}, el("span", { class: "badge ok" }, `zapisano ${r.code} v${r.version}`), kvTable(r.fractions))));
      loadProfiles();
    }));
    p1.append(el("div", { class: "actions" }, save), out1);
    root.appendChild(p1);

    // --- list profiles ---
    const p2 = el("div", { class: "panel" }, el("h2", {}, "Zapisane profile"));
    const list = el("div", { class: "muted" }, "…");
    p2.appendChild(list); root.appendChild(p2);
    async function loadProfiles() {
      try {
        const rows = await api("/gas/profiles");
        list.replaceWith(rows.length
          ? dataTable(["code", "name", "version", "status"], rows, ["code", "name", "status"])
          : el("div", { class: "muted" }, "Brak własnych profili."));
      } catch { /* ignore */ }
    }
    // reassign list ref after replace
    const listWrap = el("div", {}); p2.appendChild(listWrap);

    // --- blend ---
    const p3 = el("div", { class: "panel" }, el("h2", {}, "Mieszanie strumieni (receptura)"));
    const streamsBox = el("div", {});
    const mkStream = (cid = "REF-GAS-E", share = 0.5) => {
      const idIn = el("input", { value: cid, placeholder: "kod profilu (np. REF-GAS-E)" });
      const shIn = el("input", { type: "number", step: "0.05", value: share });
      const del = el("button", { class: "btn secondary", title: "usuń" }, "✕");
      const rowEl = el("div", { class: "streamrow" }, field("Profil / kod", idIn), field("Udział", shIn), del);
      del.addEventListener("click", () => rowEl.remove());
      rowEl._get = () => ({ compositionId: idIn.value.trim(), share: parseFloat(shIn.value) });
      return rowEl;
    };
    streamsBox.append(mkStream("REF-GAS-E", 0.7), mkStream("REF-STREAM-H2-ELX", 0.3));
    const addBtn = el("button", { class: "btn secondary" }, "+ strumień");
    addBtn.addEventListener("click", () => streamsBox.appendChild(mkStream("REF-STREAM-SNG", 0.1)));
    const saveRecipe = el("input", { type: "checkbox" });
    const recipeName = el("input", { value: "Receptura 1", placeholder: "nazwa receptury" });
    const out3 = el("div", {});
    const blendBtn = el("button", { class: "btn" }, "Mieszaj");
    blendBtn.addEventListener("click", () => withBusy(blendBtn, async () => {
      const streams = [...streamsBox.children].map((c) => c._get()).filter((s) => s.compositionId);
      const r = await api("/gas/blend", { method: "POST", body: { streams } });
      let extra = null;
      if (saveRecipe.checked) {
        const rec = await api("/gas/recipes", { method: "POST", body: { name: recipeName.value, streams } });
        extra = el("div", { class: "rowline" }, el("span", { class: "badge ok" }, `receptura ${rec.code} v${rec.version}`), el("span", { class: "mono muted" }, rec.configChecksum));
      }
      out3.replaceChildren(resultPanel(el("div", {},
        kvTable({ "Wobbe [MJ/m³]": r.wobbeIndex.value, "Ciepło spalania [MJ/m³]": r.grossCalorificValue.value, "Gęstość względna": r.relativeDensity }),
        el("h3", {}, "Skład wynikowy"), kvTable(r.composition), extra)));
    }));
    p3.append(streamsBox, el("div", { class: "actions" }, addBtn),
      el("div", { class: "grid" }, field("Zapisz jako recepturę?", saveRecipe), field("Nazwa receptury", recipeName)),
      el("div", { class: "actions" }, blendBtn), out3);
    root.appendChild(p3);

    // load list into listWrap
    try {
      const rows = await api("/gas/profiles");
      listWrap.appendChild(rows.length ? dataTable(["code", "name", "version", "status"], rows, ["code", "name", "status"]) : el("div", { class: "muted" }, "Brak własnych profili."));
      list.remove();
    } catch { list.textContent = "—"; }
  },
};

// 2. Jakość i propan ------------------------------------------------------------
screens.quality = {
  title: "Jakość i propan", icon: "✅", step: "Gaz",
  sub: "Oceń gaz wobec jawnie wybranego, wersjonowanego zestawu wymagań. Gdy parametry są poza normą, System proponuje kondycjonowanie (dodatek propanu lub balastowanie azotem).",
  async render(root) {
    const p = el("div", { class: "panel" }, el("h2", {}, "Ocena zgodności"));
    const comp = compositionField({ methane: 0.68, hydrogen: 0.30, ethane: 0.013, nitrogen: 0.006, carbon_dioxide: 0.001 });
    const setSel = el("select", {}, el("option", { value: "" }, "domyślny (wbudowany grupa E)"));
    p.append(comp.node, el("div", { class: "grid" }, field("Zestaw wymagań (wersjonowany)", setSel)));
    const out = el("div", {});
    const btn = el("button", { class: "btn" }, "Sprawdź jakość");
    btn.addEventListener("click", () => withBusy(btn, async () => {
      const g = comp.get(); if (!g) return toast("Nieprawidłowy JSON składu.");
      const body = { gasComposition: g };
      if (setSel.value) body.requirementSetId = setSel.value;
      const r = await api("/gas/quality-check", { method: "POST", body });
      const badge = r.withinSpec ? el("span", { class: "badge ok" }, "zgodny") : el("span", { class: "badge err" }, "niezgodny");
      const nodes = [el("div", { class: "rowline" }, badge, el("span", { class: "pill" }, r.requirementSet)),
        kvTable({ "Wobbe [MJ/m³]": r.wobbeIndex.value, "Ciepło spalania [MJ/m³]": r.grossCalorificValue.value, "Gęstość względna": r.relativeDensity })];
      if (r.violations.length) nodes.push(el("div", { class: "warnbox" }, el("strong", {}, "Parametry niespełnione:"), el("ul", {}, ...r.violations.map((v) => el("li", {}, v)))));
      if (r.proposal) nodes.push(el("h3", {}, "Propozycja kondycjonowania"),
        kvTable({ "Metoda": r.proposal.action, "Dodatek": r.proposal.additive, "Udział dodatku [mol]": r.proposal.additiveFractionMol, "Wobbe po [MJ/m³]": r.proposal.resultingWobbe.value, "Ciepło po [MJ/m³]": r.proposal.resultingGrossCv.value, "Uwaga": r.proposal.note }));
      out.replaceChildren(resultPanel(el("div", {}, ...nodes)));
    }));
    p.append(el("div", { class: "actions" }, btn), out);
    root.appendChild(p);
    try {
      const sets = await api("/gas/quality-requirement-sets");
      for (const s of sets) setSel.appendChild(el("option", { value: s.code }, `${s.code} v${s.version} — ${s.name}`));
    } catch { /* ignore */ }
  },
};

// 3. Spalanie i emisje ----------------------------------------------------------
screens.combustion = {
  title: "Spalanie i emisje", icon: "🔥", step: "Emisje",
  sub: "CO₂ liczone ze składu paliwa i bilansu węgla (nie z pojedynczego współczynnika), z zapotrzebowaniem powietrza, składem spalin i rozdziałem CO₂ kopalny/biogeniczny.",
  async render(root) {
    const p = el("div", { class: "panel" }, el("h2", {}, "Emisje ze spalania"));
    const comp = compositionField({ methane: 0.95, ethane: 0.03, propane: 0.02 });
    const o2 = el("input", { type: "number", step: "0.5", value: 3.0 });
    const eff = el("input", { type: "number", step: "0.05", value: 0.9 });
    p.append(comp.node, el("div", { class: "grid" }, field("O₂ w spalinach suchych [%]", o2), field("Sprawność użyteczna", eff)));
    const out = el("div", {});
    const btn = el("button", { class: "btn" }, "Licz emisje");
    btn.addEventListener("click", () => withBusy(btn, async () => {
      const g = comp.get(); if (!g) return toast("Nieprawidłowy JSON składu.");
      const r = await api("/combustion/emissions", { method: "POST", body: { gasComposition: g, options: { flueO2DryPct: parseFloat(o2.value), usefulEfficiency: parseFloat(eff.value) } } });
      out.replaceChildren(resultPanel(el("div", {},
        el("div", { class: "rowline" }, el("span", { class: "pill" }, `metoda: ${r.method}`), el("span", { class: "pill" }, `λ = ${fmt(r.excessAirRatio)}`)),
        kvTable({
          "CO₂ [kg/GJ wej.]": r.co2KgPerGjInput, "CO₂ [kg/GJ użyt.]": r.co2KgPerGjUseful,
          "CO₂ [kg/Nm³]": r.co2KgPerNm3Fuel, "CO₂ całk. [mol/mol]": r.co2TotalMolPerMol,
          "w tym kopalny": r.co2FossilMolPerMol, "w tym biogeniczny": r.co2BiogenicMolPerMol,
          "Zapotrz. powietrza [mol/mol]": r.theoreticalAirMolPerMol,
        }),
        el("h3", {}, "Spaliny suche"), kvTable(r.flueGasDry), warnBox(r.warnings))));
    }));
    p.append(el("div", { class: "actions" }, btn), out);
    root.appendChild(p);
  },
};

// 4. Technologie ekspansji ------------------------------------------------------
screens.expanders = {
  title: "Technologie ekspansji", icon: "⚙️", step: "Procesy",
  sub: "Porównanie pięciu klas technologii odzysku energii z redukcji ciśnienia w jednym punkcie pracy: moc, sprawność, temperatura wylotu, podgrzew, potencjał chłodu, ekonomika.",
  async render(root) {
    const p = el("div", { class: "panel" }, el("h2", {}, "Punkt pracy stacji redukcyjnej"));
    const comp = compositionField({ methane: 0.96, ethane: 0.03, nitrogen: 0.01 });
    const pin = el("input", { type: "number", step: "0.5", value: 5.0 });
    const pout = el("input", { type: "number", step: "0.5", value: 1.0 });
    const tin = el("input", { type: "number", step: "1", value: 320 });
    const mdot = el("input", { type: "number", step: "1", value: 20 });
    const econ = el("input", { type: "checkbox" }); econ.checked = true;
    p.append(comp.node, el("div", { class: "grid" },
      field("Ciśnienie wlot [MPa]", pin), field("Ciśnienie wylot [MPa]", pout),
      field("Temp. wlot [K]", tin), field("Strumień [kg/s]", mdot), field("Ekonomika?", econ)));
    const out = el("div", {});
    const btn = el("button", { class: "btn" }, "Porównaj 5 klas");
    btn.addEventListener("click", () => withBusy(btn, async () => {
      const g = comp.get(); if (!g) return toast("Nieprawidłowy JSON składu.");
      const body = {
        gasComposition: g, inletPressure: { value: +pin.value, unit: "MPa" },
        outletPressureTarget: { value: +pout.value, unit: "MPa" },
        inletTemperature: { value: +tin.value, unit: "K" }, massFlowRate: { value: +mdot.value, unit: "kg/s" },
      };
      if (econ.checked) body.costModel = { specificCapexPlnPerKw: 4000, fixedOpexPctPerYear: 0.03, electricityPricePlnPerMwh: 450, discountRate: 0.08, horizonYears: 15, operatingHoursPerYear: 8000 };
      const r = await api("/devices/compare-expanders", { method: "POST", body });
      const cols = ["name", "feasible", "effectiveEfficiency", "recoveredPowerKw", "outletTemperatureK", "preheatDutyKw", "coolingPotentialKw"];
      if (econ.checked) cols.push("npvPln", "lcoePlnPerMwh");
      out.replaceChildren(resultPanel(el("div", {},
        el("p", { class: "muted" }, `Punkt: ${fmt(r.operatingPoint.inletPressureMPa)}→${fmt(r.operatingPoint.outletPressureMPa)} MPa, ${fmt(r.operatingPoint.massFlowKgS)} kg/s · ${r.resultClass}`),
        dataTable(cols, r.rows, ["name"]))));
    }));
    p.append(el("div", { class: "actions" }, btn), out);
    root.appendChild(p);
  },
};

// 5. Ekonomika ------------------------------------------------------------------
screens.finance = {
  title: "Ekonomika (DCF)", icon: "💰", step: "Ekonomika",
  sub: "Wspólny silnik ekonomiczny: NPV, IRR, LCOE. Wartości roczne można podać jako jedną liczbę (powielaną) lub listę.",
  async render(root) {
    const p = el("div", { class: "panel" }, el("h2", {}, "Analiza DCF"));
    const capex = el("input", { type: "number", value: 10000000 });
    const rate = el("input", { type: "number", step: "0.01", value: 0.08 });
    const horizon = el("input", { type: "number", value: 15 });
    const opex = el("input", { value: "300000" });
    const revenue = el("input", { value: "1500000" });
    const output = el("input", { value: "16000" });
    const lco = el("select", {}, ...["LCOE", "LCOH", "LCOHeat", "LCOS"].map((k) => el("option", {}, k)));
    p.append(el("div", { class: "grid" },
      field("CAPEX [PLN]", capex), field("Stopa dyskontowa", rate), field("Horyzont [lata]", horizon),
      field("OPEX/rok [PLN]", opex), field("Przychód/rok [PLN]", revenue), field("Produkcja/rok [MWh]", output), field("Rodzaj LCO", lco)));
    const out = el("div", {});
    const listOf = (s) => s.split(/[,;\s]+/).filter(Boolean).map(Number);
    const btn = el("button", { class: "btn" }, "Licz NPV / IRR / LCOE");
    btn.addEventListener("click", () => withBusy(btn, async () => {
      const r = await api("/finance/dcf", { method: "POST", body: {
        capex: +capex.value, discountRate: +rate.value, horizonYears: +horizon.value,
        opexPerYear: listOf(opex.value), revenuePerYear: listOf(revenue.value),
        outputPerYear: listOf(output.value), lcoKind: lco.value,
      } });
      out.replaceChildren(resultPanel(el("div", {},
        kvTable({ "NPV [PLN]": r.npv, "IRR": r.irr === null ? "nieokreślone" : r.irr, [`${r.lcoKind || "LCO"} [PLN/j.]`]: r.lcoValue }),
        warnBox(r.warnings))));
    }));
    p.append(el("div", { class: "actions" }, btn), out);
    root.appendChild(p);
  },
};

// 6. Merit order ----------------------------------------------------------------
screens.merit = {
  title: "Merit order", icon: "📊", step: "Benchmarking",
  sub: "Ranking technologii wg kosztu krańcowego (paliwo + energia pomocnicza + emisje + OPEX zmienny), osobno dla energii i ciepła. Niezgodne jednostki funkcjonalne są blokowane.",
  async render(root) {
    const p = el("div", { class: "panel" }, el("h2", {}, "Zestawienie technologii"));
    const product = el("select", {}, el("option", { value: "electricity" }, "energia elektryczna"), el("option", { value: "heat" }, "ciepło"));
    const box = el("div", {});
    const mkTech = (t) => {
      const f = {}; const inp = (v, step) => el("input", { value: v, step, type: typeof v === "number" ? "number" : "text" });
      f.techId = inp(t.techId); f.name = inp(t.name); f.functionalUnit = inp(t.functionalUnit);
      f.efficiency = inp(t.efficiency, "0.01"); f.fuelPricePerMwh = inp(t.fuelPricePerMwh, "1");
      f.emissionFactorTPerMwhFuel = inp(t.emissionFactorTPerMwhFuel, "0.001"); f.co2PricePerT = inp(t.co2PricePerT, "1");
      f.variableOpexPerMwh = inp(t.variableOpexPerMwh, "1");
      const del = el("button", { class: "btn secondary" }, "✕");
      const row = el("div", { class: "panel", style: "padding:.6rem" },
        el("div", { class: "grid" },
          field("ID", f.techId), field("Nazwa", f.name), field("Jedn. funkc.", f.functionalUnit),
          field("Sprawność", f.efficiency), field("Cena paliwa [PLN/MWh]", f.fuelPricePerMwh),
          field("Wsp. emisji [t/MWh]", f.emissionFactorTPerMwhFuel), field("Cena CO₂ [PLN/t]", f.co2PricePerT),
          field("OPEX zm. [PLN/MWh]", f.variableOpexPerMwh)),
        el("div", { class: "actions" }, del));
      del.addEventListener("click", () => row.remove());
      row._get = () => ({ techId: f.techId.value, name: f.name.value, functionalUnit: f.functionalUnit.value,
        efficiency: +f.efficiency.value, fuelPricePerMwh: +f.fuelPricePerMwh.value,
        emissionFactorTPerMwhFuel: +f.emissionFactorTPerMwhFuel.value, co2PricePerT: +f.co2PricePerT.value,
        variableOpexPerMwh: +f.variableOpexPerMwh.value });
      return row;
    };
    box.append(
      mkTech({ techId: "CCGT", name: "Blok gazowo-parowy", functionalUnit: "MWh_e", efficiency: 0.58, fuelPricePerMwh: 120, emissionFactorTPerMwhFuel: 0.202, co2PricePerT: 350, variableOpexPerMwh: 8 }),
      mkTech({ techId: "OCGT", name: "Turbina gazowa", functionalUnit: "MWh_e", efficiency: 0.38, fuelPricePerMwh: 120, emissionFactorTPerMwhFuel: 0.202, co2PricePerT: 350, variableOpexPerMwh: 5 }),
    );
    const add = el("button", { class: "btn secondary" }, "+ technologia");
    add.addEventListener("click", () => box.appendChild(mkTech({ techId: "NEW", name: "Nowa", functionalUnit: "MWh_e", efficiency: 0.5, fuelPricePerMwh: 100, emissionFactorTPerMwhFuel: 0.2, co2PricePerT: 350, variableOpexPerMwh: 5 })));
    const out = el("div", {});
    const btn = el("button", { class: "btn" }, "Zbuduj merit order");
    btn.addEventListener("click", () => withBusy(btn, async () => {
      try {
        const r = await api("/merit-order", { method: "POST", body: { product: product.value, technologies: [...box.children].map((c) => c._get()) } });
        out.replaceChildren(resultPanel(el("div", {},
          el("p", { class: "muted" }, `Jednostka: ${r.functionalUnit} · metoda: ${r.method}`),
          dataTable(["rank", "techId", "name", "marginalCost", "dataQuality"], r.ranking.map((x) => ({ ...x, name: x.name })), ["techId", "name", "dataQuality"]),
          el("h3", {}, "Dekompozycja kosztu krańcowego"),
          dataTable(["techId", "fuel", "aux", "emission", "varopex", "total"], r.ranking.map((x) => ({ techId: x.techId, ...x.decomposition })), ["techId"]),
          warnBox(r.notes), el("p", { class: "mono muted" }, r.metadata.configChecksum))));
      } catch (e) {
        if (e.status === 409) out.replaceChildren(resultPanel(el("div", { class: "warnbox" }, el("strong", {}, "Ranking zablokowany (niekompatybilne): "), e.message)));
        else throw e;
      }
    }));
    p.append(el("div", { class: "grid" }, field("Produkt", product)), box, el("div", { class: "actions" }, add, btn), out);
    root.appendChild(p);
  },
};

// 7. Ceny i prognozy ------------------------------------------------------------
screens.prices = {
  title: "Ceny i prognozy", icon: "📈", step: "Ceny",
  sub: "Punkt startowy prognozy w czterech trybach (okno 30 dni z agregacją, data użytkownika, wartość użytkownika, indeks). „30 dni ≠ 30 obserwacji”. Wykres łączy historię i prognozę z oznaczoną granicą.",
  async render(root) {
    const p = el("div", { class: "panel" }, el("h2", {}, "Ścieżka cenowa"));
    const series = el("select", {});
    const mode = el("select", {}, el("option", { value: "current" }, "aktualny (okno)"), el("option", { value: "user_date" }, "data użytkownika"), el("option", { value: "user_value" }, "wartość użytkownika"), el("option", { value: "index" }, "indeks"));
    const win = el("input", { type: "number", value: 30 });
    const agg = el("select", {}, ...["mean", "median", "last", "volume_weighted"].map((a) => el("option", {}, a)));
    const refDate = el("input", { type: "date", value: "2026-05-15" });
    const userVal = el("input", { type: "number", value: 200 });
    const horizon = el("input", { type: "number", value: 5 });
    p.append(el("div", { class: "grid" },
      field("Seria", series), field("Tryb punktu startowego", mode), field("Okno [dni]", win),
      field("Agregacja", agg), field("Data odniesienia", refDate), field("Wartość użytkownika", userVal), field("Horyzont [lata]", horizon)));
    const out = el("div", {});
    const chart = el("div", { class: "chart" });
    const btn = el("button", { class: "btn" }, "Wyznacz punkt + prognoza");
    btn.addEventListener("click", () => withBusy(btn, async () => {
      const body = { mode: mode.value, windowDays: +win.value, aggregation: agg.value, horizonYears: +horizon.value };
      if (mode.value === "user_date") body.referenceDate = refDate.value;
      if (mode.value === "user_value") { body.userValue = +userVal.value; body.userNote = "wprowadzone w GUI"; }
      if (mode.value === "index") { body.indexCode = "EU_ETS_EUA"; body.indexFactor = 1.2; }
      const r = await api(`/prices/${series.value}/forecast`, { method: "POST", body });
      const sp = r.startPoint;
      out.replaceChildren(resultPanel(el("div", {},
        kvTable({ "Punkt startowy": `${fmt(sp.value)} ${sp.unit}`, "Tryb": sp.mode, "Metoda agregacji": sp.method,
          "Data odniesienia": sp.referenceDate, "Okno [dni]": sp.windowDays, "Liczba obserwacji w oknie": sp.observationsUsed,
          "Granica historia/prognoza": r.boundaryDate }),
        warnBox(sp.warnings.concat(r.notes)))));
      const q = new URLSearchParams({ mode: mode.value, windowDays: win.value, aggregation: agg.value, horizon: horizon.value });
      chart.replaceChildren(el("img", { class: "chart", src: `${API}/prices/${series.value}/forecast-chart.svg?${q}`, alt: "wykres" }));
    }));
    p.append(el("div", { class: "actions" }, btn), out, chart);
    root.appendChild(p);
    try {
      const s = await api("/prices");
      for (const x of s) series.appendChild(el("option", { value: x.code }, `${x.name} (${fmt(x.current.value)} ${x.unit})`));
    } catch { /* ignore */ }
  },
};

// 8. Raport ---------------------------------------------------------------------
screens.report = {
  title: "Raport techniczny", icon: "📄", step: "Raport",
  sub: "Wygeneruj raport techniczny z metadanymi, klasą jakości i sumą kontrolną. Podaj bloki wyników w formacie JSON (można wkleić wyniki z innych ekranów).",
  async render(root) {
    const p = el("div", { class: "panel" }, el("h2", {}, "Generator raportu"));
    const title = el("input", { value: "Raport analizy wariantu" });
    const project = el("input", { value: "Projekt 1" });
    const author = el("input", { value: "analityk" });
    const blocks = el("textarea", { spellcheck: "false", style: "min-height:160px" },
      JSON.stringify([{ title: "Spalanie i emisje", resultClass: "engineering", inputs: { metan: 0.95, propan: 0.05 }, outputs: { "CO2 kg/GJ": 50.24 }, warnings: [] }], null, 2));
    p.append(el("div", { class: "grid" }, field("Tytuł", title), field("Projekt", project), field("Autor", author)),
      field("Bloki wyników (JSON)", blocks));
    const out = el("div", {});
    const btn = el("button", { class: "btn" }, "Generuj raport");
    const openBtn = el("button", { class: "btn secondary" }, "Otwórz HTML w nowej karcie");
    const buildBody = () => ({ title: title.value, project: project.value, author: author.value, blocks: parseJSON(blocks.value, []) });
    btn.addEventListener("click", () => withBusy(btn, async () => {
      const b = buildBody(); if (!Array.isArray(b.blocks)) return toast("Bloki muszą być listą JSON.");
      const r = await api("/reports/technical", { method: "POST", body: b });
      const frame = el("iframe", { style: "width:100%;height:520px;border:1px solid var(--border);border-radius:8px;background:#fff" });
      out.replaceChildren(resultPanel(el("div", {}, el("div", { class: "rowline" }, el("span", { class: "badge ok" }, "wygenerowano"), el("span", { class: "mono muted" }, r.configChecksum)), frame)));
      frame.srcdoc = r.html;
    }));
    openBtn.addEventListener("click", async () => {
      const b = buildBody();
      const res = await fetch(`${API}/reports/technical.html`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) });
      const html = await res.text(); const w = window.open("", "_blank"); w.document.write(html); w.document.close();
    });
    p.append(el("div", { class: "actions" }, btn, openBtn), out);
    root.appendChild(p);
  },
};

// 9. Projekty i warianty --------------------------------------------------------
screens.projects = {
  title: "Projekty i warianty", icon: "🗂️", step: "Start",
  sub: "Kontenery inicjatyw oceny: projekt → warianty → wyniki. Wyniki są niezmienne i identyfikowane sumą kontrolną. Tworzenie wymaga roli ≥ analityk.",
  async render(root) {
    const p1 = el("div", { class: "panel" }, el("h2", {}, "Nowy projekt"));
    const name = el("input", { value: "Projekt oceny B+R" });
    const org = el("input", { value: "Dział rozwoju" });
    const variants = el("input", { value: "Wariant bazowy, Wariant z odzyskiem energii", placeholder: "warianty po przecinku" });
    p1.append(el("div", { class: "grid" }, field("Nazwa projektu", name), field("Jednostka organizacyjna", org)),
      field("Warianty (po przecinku)", variants));
    const out1 = el("div", {});
    const btn = el("button", { class: "btn" }, "Utwórz projekt");
    btn.addEventListener("click", () => withBusy(btn, async () => {
      const vlist = variants.value.split(",").map((s) => s.trim()).filter(Boolean).map((n) => ({ name: n }));
      try {
        await api("/projects", { method: "POST", body: { name: name.value, orgUnit: org.value, variants: vlist } });
        out1.replaceChildren(el("span", { class: "badge ok" }, "utworzono projekt"));
        loadList();
      } catch (e) {
        if (e.status === 401 || e.status === 403) out1.replaceChildren(el("div", { class: "warnbox" }, "Brak uprawnień: zaloguj się jako analityk (przycisk „Zaloguj” u góry). " + e.message));
        else throw e;
      }
    }));
    p1.append(el("div", { class: "actions" }, btn, out1));
    root.appendChild(p1);

    const p2 = el("div", { class: "panel" }, el("h2", {}, "Projekty"));
    const listWrap = el("div", { class: "muted" }, "…");
    p2.appendChild(listWrap);
    root.appendChild(p2);

    async function loadList() {
      try {
        const rows = await api("/projects");
        if (!rows.length) { listWrap.replaceChildren(el("div", { class: "muted" }, "Brak projektów.")); return; }
        const cards = rows.map((pr) => {
          const vrows = pr.variants.map((v) => ({
            wariant: v.name, status: v.status, wyniki: v.results.length,
          }));
          return el("div", { class: "panel", style: "padding:.7rem" },
            el("div", { class: "rowline" }, el("strong", {}, `#${pr.id} ${pr.name}`), el("span", { class: "pill" }, pr.orgUnit || "—")),
            pr.variants.length
              ? dataTable(["wariant", "status", "wyniki"], vrows, ["wariant", "status"])
              : el("div", { class: "muted" }, "Brak wariantów."));
        });
        listWrap.replaceChildren(...cards);
      } catch (e) { listWrap.replaceChildren(el("div", { class: "muted" }, "Nie udało się pobrać: " + e.message)); }
    }
    loadList();
  },
};

// ---------- auth UI -----------------------------------------------------------
const DEV_TOKENS = [
  { token: "dev-viewer", label: "użytkownik (viewer)" },
  { token: "dev-analyst", label: "analityk" },
  { token: "dev-approver", label: "zatwierdzający" },
  { token: "dev-admin", label: "administrator" },
];
async function renderAuth() {
  const area = $("#auth-area");
  let who = null;
  try { who = await api("/auth/whoami"); } catch { who = null; }
  area.replaceChildren();
  if (who && !who.authEnabled) {
    area.appendChild(el("span", { class: "who muted" }, "tryb dev (bez logowania)"));
    return;
  }
  if (who && who.username && who.username !== "anonymous") {
    area.append(
      el("span", { class: "who" }, "użytkownik: ", el("b", {}, `${who.username} · ${who.role}`)),
      el("button", { class: "btn secondary", onclick: () => { authToken = ""; localStorage.removeItem("egsd_token"); refreshAll(); } }, "Wyloguj"),
    );
  } else {
    area.appendChild(el("button", { class: "btn", onclick: loginModal }, "Zaloguj"));
  }
}
function loginModal() {
  const tokenInput = el("input", { placeholder: "token dostępu", value: "dev-analyst" });
  const sel = el("select", {}, el("option", { value: "" }, "— wybierz przykładowy token —"),
    ...DEV_TOKENS.map((t) => el("option", { value: t.token }, t.label)));
  sel.addEventListener("change", () => { if (sel.value) tokenInput.value = sel.value; });
  const back = el("div", { class: "modal-back" });
  const close = () => back.remove();
  const modal = el("div", { class: "modal" },
    el("h2", {}, "Logowanie"),
    el("p", { class: "muted" }, "Podaj token dostępu. W trybie demonstracyjnym dostępne są tokeny ról (docelowo SSO korporacyjne)."),
    field("Rola przykładowa", sel), field("Token", tokenInput),
    el("div", { class: "actions" },
      el("button", { class: "btn", onclick: async () => {
        authToken = tokenInput.value.trim();
        try {
          const who = await api("/auth/whoami");
          if (who.authEnabled === false) toast("Uwierzytelnianie wyłączone na serwerze (tryb dev).");
          if (who.username === "anonymous") throw new Error("token nieuznany");
          localStorage.setItem("egsd_token", authToken); close(); refreshAll();
        } catch (e) { authToken = ""; toast("Logowanie nieudane: " + e.message); }
      } }, "Zaloguj"),
      el("button", { class: "btn secondary", onclick: close }, "Anuluj")));
  back.addEventListener("click", (e) => { if (e.target === back) close(); });
  back.appendChild(modal);
  document.body.appendChild(back);
}
function refreshAll() { renderAuth(); route(); }

// ---------- shell / router ----------------------------------------------------
const NAV_ORDER = ["start", "projects", "profiles", "quality", "combustion", "expanders", "finance", "merit", "prices", "report"];
function buildNav() {
  const nav = $("#nav");
  let lastStep = null;
  for (const key of NAV_ORDER) {
    const s = screens[key];
    if (s.step && s.step !== lastStep) { nav.appendChild(el("div", { class: "navstep" }, s.step)); lastStep = s.step; }
    const item = el("div", { class: "navitem", "data-key": key },
      el("span", { class: "ico" }, s.icon), el("span", {}, s.title));
    item.addEventListener("click", () => (location.hash = key));
    nav.appendChild(item);
  }
}
async function route() {
  const key = (location.hash.replace("#", "") || "start");
  const s = screens[key] || screens.start;
  for (const it of document.querySelectorAll(".navitem")) it.classList.toggle("active", it.dataset.key === key);
  const content = $("#content");
  content.replaceChildren(el("h1", { class: "screen-title" }, s.title), el("p", { class: "screen-sub" }, s.sub));
  try { await s.render(content); }
  catch (e) { content.appendChild(el("div", { class: "warnbox" }, "Nie udało się załadować ekranu: " + e.message)); }
}
async function boot() {
  buildNav();
  window.addEventListener("hashchange", route);
  await renderAuth();
  await route();
  try {
    const h = await fetch("/health").then((r) => r.json());
    $("#engine-badge").textContent = "silnik " + h.engineVersion;
    $("#engine-badge").className = "badge ok";
  } catch { $("#engine-badge").textContent = "offline"; $("#engine-badge").className = "badge err"; }
}
boot();
