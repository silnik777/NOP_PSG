# e-GSD — zwalidowany rdzeń (walking skeleton)

Webowa platforma wspomagania decyzji strategicznych i oceny projektów B&R dla operatora
systemu dystrybucyjnego gazu (OSD). Ten przyrost dostarcza **matematycznie zweryfikowany
rdzeń** (nie makietę): centralny silnik właściwości gazów (GERG-2008 przez CoolProp),
Moduł I (sprężanie) oraz model danych Projekt/Wariant/Wynik z audytem.

> 📖 **Nie wiesz, jak to obsługiwać?** Przeczytaj poradnik krok po kroku:
> [`docs/JAK_UZYWAC.md`](docs/JAK_UZYWAC.md) — uruchomienie, obsługa przez `/docs`
> (Swagger) i gotowe przykłady do wklejenia.

## Architektura

Modularny monolit w stylu Clean Architecture / DDD:

```
src/egsd/
  domain/          # encje i reguły domenowe (bez zależności od IO)
  application/     # przypadki użycia (usługi)
  infrastructure/  # adapter CoolProp, ISO 6976, persystencja SQLAlchemy
  api/             # FastAPI, kontrakty (DTO) zgodne z OPZ
```

Silnik gazowy (`GasPropertyEngine`) jest **bezstanowy** i wymienny — zgodnie z W1.1 może
zostać wydzielony jako niezależna usługa.

## Uruchomienie (lokalnie, SQLite — bez zależności zewnętrznych)

```bash
pip install -e ".[dev]"
uvicorn egsd.api.main:app --reload      # http://127.0.0.1:8000/docs
pytest                                  # testy, w tym TV-M1-001
```

Domyślnie baza to plik SQLite (`EGSD_DATABASE_URL` nieustawione). Schemat tworzony jest
automatycznie przy starcie (tryb dev).

## Uruchomienie produkcyjne (PostgreSQL + Docker)

```bash
docker compose up --build               # app na :8000, Postgres na :5432
```

## Endpointy (v1)

- `POST /api/v1/gas-engine/point-properties` — właściwości termodynamiczne punktu (§2.1 OPZ).
- `POST /api/v1/gas-engine/combustion` — ciepło spalania i liczba Wobbego (ISO 6976).
- `POST /api/v1/thermo/compression` — Moduł I: sprężanie (Karta Modułu I).
- `POST /api/v1/hydraulics/steady-flow` — Moduł II: przepływ ustalony (Colebrook-White).
- `POST /api/v1/hydraulics/linepack` — Moduł II: pojemność akumulacyjna (linepack).
- `POST /api/v1/gas/blend` — własna kompozycja z blendowania strumieni (gaz sieciowy +
  wodór z elektrolizy + SNG z metanizacji) procentowo.
- `POST /api/v1/gas/quality-check` — ocena jakości vs standard gazu wysokometanowego (grupa E);
  gdy parametry spadną poniżej normy, proponowana jest **propanizacja** (lub balastowanie N₂).
- `POST /api/v1/storage/caes` — magazynowanie energii w sprężonym powietrzu (CAES).
- `POST /api/v1/storage/linepack` — magazyn w linepacku (widok magazynowy).
- `GET  /api/v1/devices` — katalog technologii sprężarek/ekspanderów (karty urządzeń).
- `POST /api/v1/devices/select-compressor` — dobór optymalnej sprężarki z bazy.
- `POST /api/v1/devices/select-expander` — dobór optymalnego ekspandera z bazy.
- `GET  /api/v1/prices` — lista serii cenowych z **ceną aktualną** (gaz TGE, energia TGE, EU ETS).
- `GET  /api/v1/prices/{code}/history?weeks=26` — historia (~pół roku wstecz).
- `GET  /api/v1/prices/{code}/trend` — trend (regresja, zmienność, średnia ruchoma).
- `GET  /api/v1/prices/scenarios/macro` — lista scenariuszy makro wg raportów (z atrybucją źródła).
- `GET  /api/v1/prices/{code}/report-scenario?anchor=true` — **scenariusz oparty na raportach**
  (ARE/PEP2040/KPEiR, Fit-for-55, EU Reference/IEA WEO) low/base/high, zakotwiczony do ceny
  bieżącej (historia = poziom odniesienia). **Zalecany** dla analiz.
- `GET  /api/v1/prices/{code}/scenario?startYear=2026&horizon=5` — scenariusz z trendu
  (fallback/orientacyjny).
- `GET  /api/v1/prices/{code}/chart.svg` — **wykres** historii (SVG, ~6 mies. + średnia ruchoma).
- `POST /api/v1/finance/dcf` — DCF: NPV, IRR (Brent), LCOE/LCOH/LCOHeat/LCOS.
- `POST /api/v1/finance/sensitivity` — analiza wrażliwości ±30% (dane do wykresu tornado, W5.1).
- `POST /api/v1/emissions/footprint` — CoreEmissionEngine: ślad CO₂e Scope 1/2/3
  (GHG Protocol, GWP AR6: CH₄=29,8, H₂=11; wodór szary vs zielony).
- `POST /api/v1/combustion/emissions` — **CoreCombustionEngine** (§27): CO₂ liczone
  **ze składu paliwa i bilansu węgla** (nie z pojedynczego współczynnika), zapotrzebowanie
  O₂/powietrza, skład spalin mokrych i suchych, nadmiar powietrza (λ lub z zadanego O₂ w
  spalinach suchych), rozdział CO₂ **kopalny/biogeniczny** (FuelOriginProfile), intensywność
  na Nm³/GJ wejściowy/GJ użyteczny; każdy wynik oznaczony metodą (EMI‑CMB‑013).
- `POST /api/v1/combustion/compare` — porównanie emisji spalania **przed i po** dodaniu
  propanu / wodoru / biometanu (EMI‑CMB‑011); dwa niezależne, oznaczone metodą uruchomienia.
- `POST /api/v1/merit-order` — **CoreMeritOrderEngine** (§29, BEN‑MER): merit order osobno dla
  energii elektrycznej i ciepła, koszt krańcowy = paliwo + energia pomocnicza + emisje + OPEX
  zmienny z **dekompozycją składników** (BEN‑MER‑009), **Gatekeeper** blokujący ranking przy
  niezgodnych jednostkach funkcjonalnych (BEN‑MER‑011 → HTTP 409), obsługa **ujemnych** kosztów
  krańcowych (BEN‑MER‑006), pełne metadane i suma kontrolna konfiguracji (BEN‑MER‑013).
- `POST /api/v1/devices/compare-expanders` — porównanie **pięciu klas** technologii ekspansji
  w jednym punkcie pracy (§25, EXP‑CMP‑001/005): turboekspander, silnik tłokowy, śrubowy,
  Roots, scroll — moc odzysku, sprawność, temperatura wylotu, podgrzew, potencjał chłodu oraz
  (opcjonalnie) CAPEX/OPEX/NPV/LCOE i emisje podgrzewu; klasy poza obwiednią oznaczane jako
  niedopuszczalne bez ekstrapolacji (EXP‑CMP‑003).
- `POST /api/v1/mcda/rank` — ranking wariantów **TOPSIS** (NPV↑, CAPEX↓, CO₂e↓, TRL↑)
  z **Gatekeeperem porównywalności** (W7.1/W7.2): niezgodne założenia makro → HTTP 409
  z listą rozbieżności.
- `POST /api/v1/export/compression` / `POST /api/v1/export/hydraulics` — eksport wyników
  inżynierskich do CSV/XLSX (`?format=csv|xlsx`).
- `POST /api/v1/projects` / `GET /api/v1/projects/{id}` — projekty i warianty (skrót).

### Jakość gazu, blendowanie i magazynowanie

- **Składniki:** obsługiwany pełny zestaw GERG-2008 (metan, etan, propan, butany, pentany,
  heksan, heptan, oktan, N₂, CO₂, H₂, O₂, CO, H₂S, argon, hel, woda) — patrz
  `COMPONENT_TO_COOLPROP` w `domain/gas/composition.py`.
- **Własne kompozycje:** `/gas/blend` łączy strumienie (np. gaz sieciowy + H₂ z elektrolizy +
  SNG z metanizacji) procentowo; profile startowe `REF-STREAM-H2-ELX`, `REF-STREAM-SNG`.
- **Propanizacja:** `/gas/quality-check` sprawdza Wobbe/ciepło spalania vs limity grupy E i przy
  spadku poniżej normy wylicza wymagany dodatek propanu (lub azotu przy przekroczeniu górnego
  limitu Wobbego). Uwaga inżynierska: dla gazu E dodatek H₂ do ~30% utrzymuje Wobbe ≥ 45, ale
  **ciepło spalania** spada poniżej 34 MJ/m³ — to ono jest wiążącym ograniczeniem.
- **CAES:** `/storage/caes` — magazynowanie energii w sprężonym powietrzu; sprężanie wielostopniowe
  z międzychłodzeniem i rozprężanie z dogrzewem (model przesiewowy [SCREENING], sprawność
  round-trip rzędu 45–50%).

### Dobór technologii maszyn (karty urządzeń)

Zamiast sztywnej sprawności, sprężanie/ekspansja **dobierają technologię z katalogu**
(`device_cards`, dane referencyjne wersjonowane):

- Technologie: sprężarki **tłokowa / śrubowa / Rootsa / spiralna / odśrodkowa**;
  ekspandery **turbo / tłokowy / śrubowy** — każda z zakresem sprężu na stopień, sprężem
  optymalnym, nominalną sprawnością izentropową, zakresem przepływu i limitem temperatury.
- **Charakterystyka sprawnościowa:** sprawność maleje z oddaleniem od sprężu optymalnego;
  poza zakresem urządzenie jest odrzucane. Dobór liczy **wymaganą liczbę stopni** i spręż na
  stopień, ocenia sprawność efektywną i **rankinguje** kandydatów.
- **Urządzenia pomocnicze:** dla sprężania — chłodnice międzystopniowe i **chłodnica końcowa**
  (ochrona powłoki gazociągu, dobór źródła: air/water-cooler, z mocą kW); dla ekspansji —
  **podgrzew wstępny** przy ryzyku hydratów/zamarzania (dobór źródła: gaz/ciepło odpadowe/elektryczny)
  oraz **reduktor dławiący** ZA maszyną, gdy nie osiąga ciśnienia docelowego.

Przykład (stacja redukcyjna 5→1 MPa, 20 kg/s): dobrany turboekspander, odzysk ~2,7 MW,
wylot jednostopniowy 207 K → proponowany podgrzew ~3,4 MW.

### Moduł II — Hydraulika (Faza II / MVP)

Pojedynczy odcinek, przepływ ustalony izotermiczny gazu ściśliwego: ogólne równanie
przepływu z współczynnikiem oporów Darcy'ego z równania **Colebrooka-White'a**, iteracja
po współczynniku ściśliwości Z (własności z `GasPropertyEngine`), liczba Reynoldsa i reżim
przepływu, oraz **linepack** = A·L·ρ_śr. Baza odniesienia przepływu przypięta jawnie
(warunki normalne 0 °C / 101,325 kPa — Nm³). Solver sieci pierścieniowej pozostaje poza
zakresem tego przyrostu (uwaga weryfikacyjna #3).

## Ważna uwaga walidacyjna

Wartości referencyjne z OPZ dla sprężania (TV-M1-001) okazały się niezgodne z modelem
real-fluid — patrz `docs/adr/0001-determinism-and-licensing.md` i `tests/integration/test_tv_m1_001.py`.
