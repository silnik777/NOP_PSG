# Jak obsługiwać program — poradnik krok po kroku

Ten program to **serwer obliczeniowy (API)** dla analiz gazowniczych z OPZ. Nie ma jeszcze
klikanego interfejsu graficznego — obsługuje się go przez **stronę dokumentacji `/docs`**
(tzw. Swagger UI), gdzie każdą funkcję można wywołać przyciskiem, wkleić dane i zobaczyć wynik.

> Jeżeli po otwarciu adresu widzisz `{"detail":"Not Found"}` — to znaczy, że serwer **działa**,
> tylko jesteś na stronie głównej, która nie ma treści. Dopisz na końcu adresu `/docs`.

---

## 1. Uruchomienie

### W GitHub Codespaces
```bash
pip install -e ".[dev]"
uvicorn egsd.api.main:app --host 0.0.0.0 --port 8000
```
Potem zakładka **Ports** → kliknij port **8000** → otworzy się przeglądarka. Jeśli wyskoczy
pusta strona lub błąd logowania, w zakładce Ports zmień widoczność portu na **Public**.
Na końcu adresu dopisz `/docs`.

> Ważne: `--host 0.0.0.0`. Bez tego przekierowany port w Codespaces bywa nieosiągalny.

### Lokalnie na komputerze
```bash
pip install -e ".[dev]"
uvicorn egsd.api.main:app --reload
```
Otwórz w przeglądarce: **http://127.0.0.1:8000/docs**

### Sprawdzenie, że żyje
Wejdź na `/health` — powinno zwrócić `{"status":"ok", ...}`.

---

## 2. Jak wykonać obliczenie w `/docs` (Swagger UI)

1. Wejdź na `/docs`. Zobaczysz listę wszystkich funkcji pogrupowanych (gas-engine, gas,
   devices, combustion, merit-order, finance, prices, emissions, …).
2. Kliknij wybraną funkcję, żeby ją rozwinąć — zobaczysz opis i przykładowe dane.
3. Kliknij przycisk **„Try it out"** (prawy górny róg sekcji).
4. W polu **Request body** wpisz/wklej dane (JSON). Możesz użyć gotowych przykładów niżej.
5. Kliknij niebieski **„Execute"**.
6. Wynik pojawia się w sekcji **Response** — kod `200` = sukces; poniżej JSON z wynikami.

Kody odpowiedzi, które zobaczysz:
- **200** — OK, są wyniki.
- **422** — błąd w danych wejściowych (np. literówka w nazwie składnika, złe ciśnienia).
- **409** — obliczenie zablokowane celowo (np. próba porównania niezgodnych wariantów).
- **404** — zły adres (np. nieznany kod profilu).

---

## 3. Najważniejsze funkcje z gotowymi przykładami

Poniższe JSON-y wklej w polu **Request body** danej funkcji i kliknij **Execute**.

### 3.1. Właściwości gazu w punkcie — `POST /api/v1/gas-engine/point-properties`
Liczy gęstość, entalpię, ściśliwość itd. dla zadanego składu, ciśnienia i temperatury.
```json
{
  "gasComposition": { "methane": 0.96, "ethane": 0.03, "nitrogen": 0.01 },
  "stateVariables": {
    "pressure": { "value": 5.0, "unit": "MPa" },
    "temperature": { "value": 283.15, "unit": "K" }
  }
}
```

### 3.2. Mieszanie profili (własny + bazowy) — `POST /api/v1/gas/blend`
Miesza kilka strumieni w zadanych udziałach. Tu: 70% gaz sieciowy + 20% wodór z elektrolizy
+ 10% SNG.
```json
{
  "streams": [
    { "compositionId": "REF-GAS-E", "share": 0.7 },
    { "compositionId": "REF-STREAM-H2-ELX", "share": 0.2 },
    { "compositionId": "REF-STREAM-SNG", "share": 0.1 }
  ]
}
```
W wyniku m.in. skład mieszaniny, liczba Wobbego, ciepło spalania.

### 3.3. Ocena jakości gazu + propan — `POST /api/v1/gas/quality-check`
Sprawdza gaz względem wymagań (grupa E) i — jeśli nie spełnia — proponuje ile dodać propanu.
```json
{
  "gasComposition": {
    "methane": 0.6755, "ethane": 0.0126, "propane": 0.0035,
    "nitrogen": 0.0056, "carbon_dioxide": 0.0028, "hydrogen": 0.30
  }
}
```
Wynik: `withinSpec` (czy spełnia), a jeśli nie — `proposal` z ilością propanu do dodania.

### 3.4. Emisje CO₂ ze spalania — `POST /api/v1/combustion/emissions`  *(nowe)*
Liczy CO₂ **ze składu paliwa i bilansu węgla** (nie z jednego współczynnika), zapotrzebowanie
powietrza, skład spalin, rozdział CO₂ kopalny/biogeniczny.
```json
{
  "gasComposition": { "methane": 0.95, "ethane": 0.03, "propane": 0.02 },
  "options": { "usefulEfficiency": 0.9, "flueO2DryPct": 3.0 }
}
```
Wynik: `co2KgPerGjInput` (kg CO₂ na GJ paliwa), `co2KgPerGjUseful` (na GJ ciepła użytecznego),
skład spalin, nadmiar powietrza.

### 3.5. Porównanie emisji przed/po propanie — `POST /api/v1/combustion/compare`  *(nowe)*
```json
{
  "baseGasComposition": { "methane": 1.0 },
  "modifiedGasComposition": { "methane": 0.9, "propane": 0.1 }
}
```
Wynik: emisje „przed" i „po" oraz różnica (`deltaCo2KgPerNm3Fuel`).

### 3.6. Porównanie 5 technologii ekspansji — `POST /api/v1/devices/compare-expanders`  *(nowe)*
Porównuje turboekspander, silnik tłokowy, śrubowy, Roots i scroll w jednym punkcie pracy
(stacja redukcyjna 5 → 1 MPa, 20 kg/s). Sekcja `costModel` jest opcjonalna — dodaje NPV/LCOE.
```json
{
  "gasComposition": { "methane": 0.96, "ethane": 0.03, "nitrogen": 0.01 },
  "inletPressure": { "value": 5.0, "unit": "MPa" },
  "outletPressureTarget": { "value": 1.0, "unit": "MPa" },
  "inletTemperature": { "value": 320.0, "unit": "K" },
  "massFlowRate": { "value": 20.0, "unit": "kg/s" },
  "costModel": {
    "specificCapexPlnPerKw": 4000, "fixedOpexPctPerYear": 0.03,
    "electricityPricePlnPerMwh": 450, "discountRate": 0.08,
    "horizonYears": 15, "operatingHoursPerYear": 8000
  }
}
```
Wynik: dla każdej z 5 klas — moc odzysku, sprawność, temperatura wylotu, potrzebny podgrzew,
potencjał chłodu oraz (gdy podasz `costModel`) CAPEX/OPEX/NPV/LCOE.

### 3.7. Merit order (kolejność technologii) — `POST /api/v1/merit-order`  *(nowe)*
Ustawia technologie w kolejności rosnącego kosztu krańcowego, osobno dla energii i ciepła.
```json
{
  "product": "heat",
  "technologies": [
    { "techId": "BOIL", "name": "Kocioł gazowy", "functionalUnit": "GJ_th",
      "efficiency": 0.92, "fuelPricePerMwh": 120, "emissionFactorTPerMwhFuel": 0.202,
      "co2PricePerT": 350, "variableOpexPerMwh": 2, "dataQuality": "literature" },
    { "techId": "HP", "name": "Pompa ciepła", "functionalUnit": "GJ_th",
      "efficiency": 1.0, "auxEnergyRatio": 0.33, "auxPricePerMwh": 450,
      "variableOpexPerMwh": 3, "dataQuality": "family" }
  ]
}
```
Wynik: ranking z rozbiciem kosztu na paliwo/pomocnicze/emisje/OPEX. Uwaga: jeśli wpiszesz
różne `functionalUnit` (np. `GJ_th` i `MWh_e`), program **celowo zablokuje** ranking (kod 409).

### 3.8. Ekonomika DCF — `POST /api/v1/finance/dcf`
NPV, IRR, LCOE. Przykład: inwestycja 10 mln, 15 lat, przychód i koszt roczny.
```json
{
  "capex": 10000000,
  "discountRate": 0.08,
  "horizonYears": 15,
  "opexPerYear": [300000],
  "revenuePerYear": [1500000],
  "outputPerYear": [16000],
  "lcoKind": "LCOE"
}
```

### 3.9. Ceny i scenariusze — funkcje `GET` (bez wpisywania danych)
Te wywołasz od razu (tylko „Try it out" → „Execute"), ewentualnie wpisując kod serii:
- `GET /api/v1/prices` — lista serii z ceną bieżącą. Dostępne kody: **`PL_GAS_TGE`**
  (gaz TGE), **`PL_POWER_TGE`** (energia TGE), **`EU_ETS_EUA`** (uprawnienia CO₂ EU ETS).
- `GET /api/v1/prices/{code}/history?weeks=26` — historia (np. `code` = `PL_GAS_TGE`).
- `GET /api/v1/prices/{code}/chart.svg` — **wykres** historii (otwórz w nowej karcie).
- `GET /api/v1/prices/{code}/report-scenario?anchor=true` — scenariusz cenowy low/base/high.

---

## 4. Pełny scenariusz OPZ (łańcuch od gazu do decyzji)

Tak wygląda typowa analiza — wykonaj funkcje po kolei, przenosząc wyniki dalej:

1. **Mieszanie** — `POST /api/v1/gas/blend` → uzyskujesz skład gazu wynikowego.
2. **Jakość** — `POST /api/v1/gas/quality-check` → czy spełnia normę; jeśli nie, ile propanu.
3. **Właściwości** — `POST /api/v1/gas-engine/point-properties` → parametry termodynamiczne.
4. **Spalanie/emisje** — `POST /api/v1/combustion/emissions` → CO₂ ze składu.
5. **Ekspansja** — `POST /api/v1/devices/compare-expanders` → dobór technologii odzysku energii.
6. **Ekonomika** — `POST /api/v1/finance/dcf` → NPV/IRR/LCOE inwestycji.
7. **Merit order** — `POST /api/v1/merit-order` → kolejność technologii wg kosztu.
8. **Porównanie wariantów** — `POST /api/v1/mcda/rank` → ranking wariantów (TOPSIS).

---

## 5. Gotowe kody profili gazu (do pola `compositionId`)

| Kod | Opis |
|-----|------|
| `REF-GAS-E` | Gaz wysokometanowy grupy E (sieciowy) |
| `REF-GAS-LW` | Gaz zaazotowany Lw |
| `REF-GAS-H2-05` / `-10` / `-20` | Gaz E z domieszką wodoru 5 / 10 / 20% |
| `REF-STREAM-H2-ELX` | Strumień wodoru z elektrolizy |
| `REF-STREAM-SNG` | Strumień SNG (metanizacja) |

Zamiast kodu możesz zawsze podać własny skład polem `gasComposition`, np.
`{ "methane": 0.9, "ethane": 0.05, "propane": 0.05 }`. Udziały nie muszą sumować się idealnie
do 1 — program je znormalizuje (dopuszczalne odchylenie do 5%).

Nazwy składników: `methane, ethane, propane, n_butane, i_butane, n_pentane, i_pentane,
n_hexane, nitrogen, carbon_dioxide, hydrogen, oxygen, carbon_monoxide, hydrogen_sulfide,
water, argon, helium` (działają też skróty: `ch4, co2, n2, h2`).

---

## 6. Najczęstsze problemy

| Objaw | Przyczyna / rozwiązanie |
|-------|-------------------------|
| `{"detail":"Not Found"}` na stronie głównej | To normalne — dopisz `/docs` do adresu. |
| Kod **422** | Błąd w danych: literówka w nazwie składnika, ciśnienie wylotu ≥ wlotu przy ekspansji, brak wymaganego pola. Sprawdź komunikat w polu `detail`. |
| Kod **409** przy merit order / MCDA | Celowa blokada — porównujesz niezgodne rzeczy (różne jednostki funkcjonalne, różne założenia makro). Ujednolić dane. |
| Port w Codespaces nie odpowiada | Uruchom z `--host 0.0.0.0` i ustaw port jako Public. |
| Nie wiem jakich pól użyć | W `/docs` każda funkcja ma sekcję **Schema** z listą pól i typów. |
