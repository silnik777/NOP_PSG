# Weryfikacja zgodności aplikacji z OPZ

Dokument ocenia, w jakim stopniu obecny stan aplikacji **e‑GSD** realizuje wymagania OPZ,
ze szczególnym uwzględnieniem **zakresu MVP (§50, kryterium ACC‑MVP‑001)**. Ocena jest
podstawą decyzji o budowie pełnego GUI.

**Data oceny:** 2026‑07‑15 · **Gałąź:** `claude/app-opz-p4c213` · **Testy:** 116 pass, 1 xfail

## Legenda statusów
- ✅ **Zrealizowane** — działa i jest pokryte testem/dowodem.
- 🟡 **Częściowe** — rdzeń działa, ale brakuje elementu wymaganego przez OPZ.
- ❌ **Brak** — funkcja nieobecna.

---

## 1. Werdykt ogólny

Aplikacja ma **mocny, zwalidowany rdzeń obliczeniowy** (termodynamika GERG‑2008, mieszanie,
jakość+propan, spalanie/emisje ze składu, 5 klas ekspanderów, ekonomika DCF, merit order,
odtwarzalność i audyt). **Nie spełnia jednak jeszcze pełnego MVP** — brakuje kilku elementów
łańcucha cenowego, trwałości/wersjonowania receptur, wyboru wersjonowanego zestawu wymagań
jakości, uwierzytelniania oraz **całego interfejsu użytkownika (GUI)**.

**Kompletność 24 elementów MVP (§50): 16 ✅ · 4 🟡 · 4 ❌.**

> Wniosek dla GUI: rdzeń jest wystarczający, by zaprojektować GUI dla ~70% ekranów już teraz,
> ale **4 luki cenowe/receptur należy domknąć w backendzie** równolegle z GUI, inaczej część
> ekranów nie będzie miała czego pokazać.

---

## 2. Macierz 24 elementów MVP (§50)

| # | Element MVP | Status | Dowód / uwaga |
|---|-------------|:------:|---------------|
| 1 | Kreator własnego profilu gazu | 🟡 | Skład można podać inline w każdej funkcji; brak zapisu i wersjonowania własnego profilu jako trwałego obiektu. |
| 2 | Wybór profilu z bazy | ✅ | `GET /api/v1/reference-profiles`, pole `compositionId`. |
| 3 | Mieszanie ≥2 profili | ✅ | `POST /api/v1/gas/blend`. |
| 4 | Mieszanie własny + bazowy | ✅ | `blend` przyjmuje w strumieniu inline `gasComposition` **lub** `compositionId`. |
| 5 | Wersjonowanie receptury | ❌ | `blend` jest bezstanowy — receptura nie jest zapisywana ani wersjonowana. |
| 6 | Podstawowe właściwości gazu | ✅ | `POST /api/v1/gas-engine/point-properties` (GERG‑2008). |
| 7 | Ocena wobec zestawu wymagań gazu wysokometanowego | 🟡 | `quality-check` ocenia wg grupy E, ale limity są zaszyte — brak **wyboru wersjonowanego** zestawu wymagań (GAS‑QLT, ZP‑001). |
| 8 | Wskazanie parametrów niespełnionych | ✅ | `quality-check` → `withinSpec` + parametry poza normą. |
| 9 | ≥1 metoda kondycjonowania | ✅ | Propanizacja / balastowanie N₂. |
| 10 | Analiza dodania propanu | ✅ | `quality-check` liczy wymagany dodatek propanu. |
| 11 | Model spalania — CO₂ ze składu | ✅ | `POST /api/v1/combustion/emissions` (bilans węgla). |
| 12 | Karta każdej z 5 klas ekspansji | ✅ | `GET /api/v1/devices` — turbo, tłokowy, śrubowy, Roots, scroll. |
| 13 | Porównanie ekspansji w punkcie pracy | ✅ | `POST /api/v1/devices/compare-expanders`. |
| 14 | Wspólny silnik ekonomiczny | ✅ | `POST /api/v1/finance/dcf` (NPV/IRR/LCOE…). |
| 15 | Merit order dla energii el. i ciepła | ✅ | `POST /api/v1/merit-order`. |
| 16 | Scenariusz cenowy z danych historycznych | ✅ | `GET /api/v1/prices/{code}/report-scenario`. |
| 17 | Punkt startowy — konfigurowalne okno, domyślnie 30 dni | ❌ | Scenariusz kotwiczy do **ostatniej** obserwacji; brak okna 30 dni i trybów agregacji (§30.3 A). |
| 18 | Możliwość wskazania własnej daty | ❌ | Brak trybu daty użytkownika (§30.3 B, PRC). |
| 19 | Możliwość wskazania własnej ceny startowej | ❌ | Brak trybu wartości użytkownika (§30.3 C, PRC). |
| 20 | Wykres historia + prognoza z granicą | 🟡 | `chart.svg` pokazuje samą historię; brak połączenia z prognozą i oznaczenia punktu przejścia (PRC‑002). |
| 21 | Pełna odtwarzalność | ✅ | `result_hash` (SHA‑256), `ResultRecord`, suma kontrolna konfiguracji. |
| 22 | Podstawowa ścieżka audytowa | ✅ | Moduł audytu + zapis uruchomień. |
| 23 | Raport techniczny | 🟡 | Jest eksport CSV/XLSX wyników; brak generowanego **raportu technicznego** (dokumentu). |
| 24 | Eksport wyników | ✅ | `POST /api/v1/export/compression`, `/export/hydraulics`. |

---

## 3. Zgodność wg rodzin wymagań funkcjonalnych

| Rodzina (OPZ) | Zakres | Status | Uwaga |
|---------------|--------|:------:|-------|
| **GAS / GAS‑MIX** (§19–20) | Właściwości, mieszanie, bilanse | ✅ | Silnik GERG‑2008; mieszanie po udziałach z bilansem. Analiza odwrotna (dobór dodatku do celu) — 🟡 tylko dla propanu w jakości. |
| **GAS‑QLT** (§21) | Ocena jakości | 🟡 | Ocena grupy E działa; brak **wybieralnych, wersjonowanych** zestawów wymagań. |
| **GAS‑CND** (§22) | Kondycjonowanie | 🟡 | Propanizacja/N₂ jako wariant; brak trybu doboru z funkcją celu i wieloma metodami. |
| **PRO** (§24) | Modele procesowe | ✅ | Sprężanie (Moduł I), hydraulika + linepack, ekspansja, CAES. |
| **EXP / EXP‑CMP** (§25) | 5 kart ekspansji + porównanie | ✅ | Katalog 5 klas + porównanie punktowe z ekonomiką i emisjami. |
| **CMB / EMI** (§27–28) | Spalanie i emisje | ✅ | CO₂ ze składu, spaliny mokre/suche, nadmiar powietrza, rozdział kopalny/biogeniczny; ślad Scope 1/2/3. |
| **ECO** (§26) | Silnik ekonomiczny | ✅ | Jeden wspólny silnik DCF; NPV/IRR/LCOE + wrażliwość (tornado). MAC — 🟡 rozszerzenie. |
| **BEN / BEN‑MER** (§29) | Merit order + benchmarking | ✅ | Merit order el./ciepło z dekompozycją i gatekeeperem; MCDA TOPSIS z blokadą porównywalności. Chłód/czasowy — rozszerzenia. |
| **PRC** (§30) | Ceny i ścieżki cenowe | 🟡 | Historia oddzielona od prognoz; scenariusze raportowe. **Brak** 4 trybów punktu startowego, okna 30 dni, wykresu historia+prognoza. |
| **DAT** (§31) | Dane referencyjne | ✅ | Wersjonowane profile, karty urządzeń, serie cenowe, scenariusze makro (seed + migracje). |

---

## 4. Wymagania przekrojowe i organizacyjne

| Obszar (OPZ) | Status | Uwaga |
|--------------|:------:|-------|
| **SEC — bezpieczeństwo/uwierzytelnianie/role** (§37, ZP‑002) | ❌ | **Brak logowania, ról i autoryzacji.** API jest otwarte. To istotna luka MVP (SEC‑001…007). Wymaga decyzji ZP‑002 (SSO SAML/OIDC/AD). |
| **UX — interfejs użytkownika** (§32) | ❌ | Brak GUI; obsługa tylko przez Swagger `/docs`. To przedmiot następnego etapu. |
| **AUD — audyt** (§38) | ✅ | Podstawowy ślad audytowy i niezmienność wyników historycznych. |
| **VAL — walidacja** (§39) | ✅ | Testy jednostkowe/integracyjne/odtwarzalności; zwalidowane wartości fizyczne. |
| **API — kontrakty** (§35) | ✅ | Udokumentowane OpenAPI (`/openapi.json`, `/docs`). |
| **INT — integracje** (§34) | 🟡 | Import serii przez seed/administratora; brak docelowego kontraktu integracyjnego danych rynkowych (ZP‑004). |
| **OPS — wdrożenie** (§43) | 🟡 | Docker + Postgres + migracje Alembic; brak pełnego CI/CD, SLA, kopii/odtworzenia. |
| **DOC — dokumentacja** (§44) | 🟡 | README, ADR, poradnik, ten raport; brak kompletu dokumentacji administratora/modeli. |
| **LIC — licencje / SBOM** (§48) | 🟡 | Zależności przypięte; `cyclonedx-bom` dostępne; brak wygenerowanego SBOM w repo. |

---

## 5. Luki blokujące pełne MVP (priorytet do domknięcia PRZED/RÓWNOLEGLE z GUI)

Uszeregowane wg wpływu na kryterium ACC‑MVP‑001:

1. **Łańcuch cenowy — punkt startowy i wykres (MVP 17–20, PRC‑002…008).** Cztery tryby
   punktu startowego (aktualny z oknem 30 dni + agregacja, data użytkownika, wartość
   użytkownika, indeks), oddzielenie i **połączenie** historii z prognozą na wykresie z
   oznaczoną granicą. *Największa pojedyncza luka MVP.*
2. **Wersjonowanie receptur mieszania i zapis własnych profili (MVP 1, 5).** Trwały obiekt
   `BlendRecipe`/`CompositionProfile` z wersją, statusem, właścicielem i możliwością
   ponownego uruchomienia.
3. **Wybieralny, wersjonowany zestaw wymagań jakości (MVP 7, GAS‑QLT, ZP‑001).** Zamiast
   zaszytej grupy E — katalog wersjonowanych zestawów wymagań wskazywanych jawnie.
4. **Uwierzytelnianie i role (SEC, ZP‑002).** Nawet minimalny mechanizm (konta + role
   z §10) jest potrzebny do wielouserowej, audytowalnej pracy.
5. **Raport techniczny (MVP 23).** Generowany dokument (PDF/HTML) z metadanymi wyniku,
   klasą jakości i ostrzeżeniami.

Elementy oznaczone w OPZ jako *rozszerzenia*/*opcje* (Monte Carlo, unit commitment, CCS/CCU,
pełne LCA, merit order chłodu/czasowy, backtesting) **są poza MVP** i nie blokują odbioru MVP.

---

## 6. Rekomendacja: sekwencja przed GUI

Proponowana kolejność, tak by GUI powstawało na kompletnym rdzeniu:

- **Krok A (backend, domknięcie MVP):** luki 1–3 i 5 z sekcji 5 (cenowy punkt startowy +
  wykres, wersjonowanie receptur/profili, wybór zestawu wymagań jakości, raport). Każda jako
  wycinek domain→application→API z testami — zgodnie z obecną architekturą.
- **Krok B (bezpieczeństwo):** minimalne uwierzytelnianie + role (luka 4), z furtką na SSO
  (ZP‑002).
- **Krok C (GUI):** pełny interfejs webowy oparty na ustabilizowanym API (patrz sekcja 7).

Kroki A i C mogą częściowo iść równolegle: ekrany dla ✅‑funkcji (mieszanie, jakość, spalanie,
ekspandery, ekonomika, merit order) można budować od razu; ekrany cenowe/receptur — po Kroku A.

---

## 7. Zakres proponowanego GUI (do akceptacji)

GUI powinno odwzorować łańcuch OPZ (B.1) jako spójny przepływ ekranów:

1. **Pulpit / Projekty → Warianty → Scenariusze** (UC‑01, UC‑16).
2. **Profile i mieszaniny gazu** — kreator składu, blend własny+bazowy, porównanie przed/po (UC‑02…04).
3. **Jakość i zgodność** — wybór zestawu wymagań, wskazanie parametrów niespełnionych (UC‑05…06).
4. **Kondycjonowanie** — analiza propanu i innych metod (UC‑07…08).
5. **Technologie ekspansji** — porównanie 5 kart w punkcie pracy (UC‑09).
6. **Spalanie i emisje** — CO₂ ze składu, spaliny, przed/po (UC‑11).
7. **Ekonomika** — DCF, wrażliwość (tornado) (UC‑12).
8. **Merit order / benchmarking** — ranking el./ciepło z dekompozycją (UC‑13).
9. **Dane i ścieżki cenowe** — historia + prognoza z granicą, tryby punktu startowego (UC‑10).
10. **Raporty, audyt, administracja** — eksport, ślad audytowy, dane referencyjne (UC‑17…22).

**Propozycja technologiczna:** front SPA (React/Vue) konsumujący istniejące API, z klientem
generowanym z OpenAPI; wykresy po stronie frontu; brak logiki obliczeniowej w przeglądarce
(zgodnie z B.3 — przeglądarka bez własnego silnika). Do potwierdzenia przez Zamawiającego.
