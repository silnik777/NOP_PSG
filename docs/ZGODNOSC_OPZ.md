# Weryfikacja zgodności aplikacji z OPZ

Dokument ocenia, w jakim stopniu obecny stan aplikacji **e‑GSD** realizuje wymagania OPZ,
ze szczególnym uwzględnieniem **zakresu MVP (§50, kryterium ACC‑MVP‑001)**. Ocena jest
podstawą decyzji o budowie pełnego GUI.

**Data oceny:** 2026‑07‑15 (aktualizacja po domknięciu luk backendu) · **Gałąź:**
`claude/app-opz-p4c213` · **Testy:** 153 pass, 1 xfail

> **Aktualizacja:** Luki 1–5 z pierwotnej wersji tego raportu zostały domknięte
> (ceny/punkt startowy+wykres, wersjonowanie receptur i profili, wybór wersjonowanego
> zestawu wymagań jakości, raport techniczny, minimalne uwierzytelnianie). **Wszystkie 24
> elementy MVP są zrealizowane.** Pozostaje budowa GUI (sekcja 7).

## Legenda statusów
- ✅ **Zrealizowane** — działa i jest pokryte testem/dowodem.
- 🟡 **Częściowe** — rdzeń działa, ale brakuje elementu wymaganego przez OPZ.
- ❌ **Brak** — funkcja nieobecna.

---

## 1. Werdykt ogólny

Aplikacja ma **mocny, zwalidowany rdzeń obliczeniowy** (termodynamika GERG‑2008, mieszanie,
jakość+propan, spalanie/emisje ze składu, 5 klas ekspanderów, ekonomika DCF, merit order,
łańcuch cenowy z punktem startowym i wykresem prognozy, wersjonowanie profili i receptur,
raport techniczny, odtwarzalność, audyt i minimalne uwierzytelnianie). Po domknięciu luk
backendu **wszystkie 24 elementy MVP są zrealizowane**; do pełnego wdrożenia pozostaje
**interfejs użytkownika (GUI)** oraz elementy eksploatacyjne (OPS/SSO/SBOM).

**Kompletność 24 elementów MVP (§50): 24 ✅.**

> Wniosek dla GUI: rdzeń jest kompletny — można budować pełne GUI dla wszystkich ekranów
> łańcucha OPZ na ustabilizowanym API (sekcja 7).

---

## 2. Macierz 24 elementów MVP (§50)

| # | Element MVP | Status | Dowód / uwaga |
|---|-------------|:------:|---------------|
| 1 | Kreator własnego profilu gazu | ✅ | `POST /api/v1/gas/profiles` — trwały, wersjonowany profil (status/właściciel); używalny jako `compositionId` wszędzie. |
| 2 | Wybór profilu z bazy | ✅ | `GET /api/v1/reference-profiles`, pole `compositionId`. |
| 3 | Mieszanie ≥2 profili | ✅ | `POST /api/v1/gas/blend`. |
| 4 | Mieszanie własny + bazowy | ✅ | `blend` przyjmuje w strumieniu inline `gasComposition` **lub** `compositionId`. |
| 5 | Wersjonowanie receptury | ✅ | `POST /api/v1/gas/recipes` (wersjonowane) + `.../{code}/run` — deterministyczne ponowne uruchomienie z sumą kontrolną. |
| 6 | Podstawowe właściwości gazu | ✅ | `POST /api/v1/gas-engine/point-properties` (GERG‑2008). |
| 7 | Ocena wobec zestawu wymagań gazu wysokometanowego | ✅ | Katalog wersjonowanych zestawów (`GET /gas/quality-requirement-sets`); `quality-check` przyjmuje `requirementSetId` i echouje zastosowany zestaw+wersję. |
| 8 | Wskazanie parametrów niespełnionych | ✅ | `quality-check` → `withinSpec` + parametry poza normą. |
| 9 | ≥1 metoda kondycjonowania | ✅ | Propanizacja / balastowanie N₂. |
| 10 | Analiza dodania propanu | ✅ | `quality-check` liczy wymagany dodatek propanu. |
| 11 | Model spalania — CO₂ ze składu | ✅ | `POST /api/v1/combustion/emissions` (bilans węgla). |
| 12 | Karta każdej z 5 klas ekspansji | ✅ | `GET /api/v1/devices` — turbo, tłokowy, śrubowy, Roots, scroll. |
| 13 | Porównanie ekspansji w punkcie pracy | ✅ | `POST /api/v1/devices/compare-expanders`. |
| 14 | Wspólny silnik ekonomiczny | ✅ | `POST /api/v1/finance/dcf` (NPV/IRR/LCOE…). |
| 15 | Merit order dla energii el. i ciepła | ✅ | `POST /api/v1/merit-order`. |
| 16 | Scenariusz cenowy z danych historycznych | ✅ | `GET /api/v1/prices/{code}/report-scenario`. |
| 17 | Punkt startowy — konfigurowalne okno, domyślnie 30 dni | ✅ | `POST /prices/{code}/start-point` tryb `current` z oknem 30 dni i agregacją (mean/median/last); „30 dni ≠ 30 obserwacji" raportowane jawnie. |
| 18 | Możliwość wskazania własnej daty | ✅ | Tryb `user_date` (§30.3 B) — dokładny zestaw obserwacji, zgłoszenie braku danych. |
| 19 | Możliwość wskazania własnej ceny startowej | ✅ | Tryb `user_value` (§30.3 C) — oznaczenie danej użytkownika + źródło. |
| 20 | Wykres historia + prognoza z granicą | ✅ | `GET /prices/{code}/forecast-chart.svg` — historia + pasmo prognozy + oznaczona granica przejścia (PRC‑002). |
| 21 | Pełna odtwarzalność | ✅ | `result_hash` (SHA‑256), `ResultRecord`, suma kontrolna konfiguracji. |
| 22 | Podstawowa ścieżka audytowa | ✅ | Moduł audytu + zapis uruchomień. |
| 23 | Raport techniczny | ✅ | `POST /reports/technical(.html)` — dokument HTML z metadanymi, klasą jakości bloków, ostrzeżeniami i sumą kontrolną. |
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
| **SEC — bezpieczeństwo/uwierzytelnianie/role** (§37, ZP‑002) | 🟡 | Minimalny mechanizm token→rola z hierarchią ról §10 (`/auth/whoami`, guard ≥ analityk na zapisie), domyślnie wyłączony (`EGSD_AUTH_ENABLED`). Docelowo SSO SAML/OIDC/AD (ZP‑002). |
| **UX — interfejs użytkownika** (§32) | 🟡 | Serwowane GUI pod `/app/` (HTML/JS bez build‑stepu) obejmujące łańcuch OPZ: profile/mieszanie, jakość+propan, spalanie, ekspandery, ekonomika, merit order, ceny+wykres, raport. Pełny UX (role w UI, i18n, dostępność) — do rozwinięcia. |
| **AUD — audyt** (§38) | ✅ | Podstawowy ślad audytowy i niezmienność wyników historycznych. |
| **VAL — walidacja** (§39) | ✅ | Testy jednostkowe/integracyjne/odtwarzalności; zwalidowane wartości fizyczne. |
| **API — kontrakty** (§35) | ✅ | Udokumentowane OpenAPI (`/openapi.json`, `/docs`). |
| **INT — integracje** (§34) | 🟡 | Import serii przez seed/administratora; brak docelowego kontraktu integracyjnego danych rynkowych (ZP‑004). |
| **OPS — wdrożenie** (§43) | 🟡 | Docker + Postgres + migracje Alembic; brak pełnego CI/CD, SLA, kopii/odtworzenia. |
| **DOC — dokumentacja** (§44) | 🟡 | README, ADR, poradnik, ten raport; brak kompletu dokumentacji administratora/modeli. |
| **LIC — licencje / SBOM** (§48) | 🟡 | Zależności przypięte; `cyclonedx-bom` dostępne; brak wygenerowanego SBOM w repo. |

---

## 5. Luki MVP — status domknięcia

Wszystkie luki blokujące z pierwotnej wersji raportu zostały **domknięte** (dowód: testy +
endpointy):

1. ✅ **Łańcuch cenowy — punkt startowy i wykres (MVP 17–20).** Cztery tryby (aktualny z oknem
   30 dni + agregacja, data użytkownika, wartość użytkownika, indeks) oraz wykres historia+
   prognoza z granicą.
2. ✅ **Wersjonowanie receptur i zapis własnych profili (MVP 1, 5).** `CompositionProfile` i
   `BlendRecipe` z wersją/statusem/właścicielem i deterministycznym ponownym uruchomieniem.
3. ✅ **Wybieralny, wersjonowany zestaw wymagań jakości (MVP 7, GAS‑QLT).** Katalog zestawów;
   jawny wybór i echo w wyniku.
4. 🟡→✅(min.) **Uwierzytelnianie i role (SEC).** Minimalny mechanizm token→rola (docelowo SSO).
5. ✅ **Raport techniczny (MVP 23).** Generowany dokument HTML z metadanymi i klasą jakości.

Elementy oznaczone w OPZ jako *rozszerzenia*/*opcje* (Monte Carlo, unit commitment, CCS/CCU,
pełne LCA, merit order chłodu/czasowy, backtesting) **są poza MVP** i nie blokują odbioru MVP.
Do pełnego wdrożenia produkcyjnego pozostają elementy eksploatacyjne (SSO docelowe, pełne
CI/CD i SLA, SBOM, komplet dokumentacji) oraz **GUI** (sekcja 7).

---

## 6. Sekwencja — stan realizacji

- **Krok A (backend, domknięcie MVP):** ✅ **wykonany** — cenowy punkt startowy + wykres,
  wersjonowanie receptur/profili, wybór zestawu wymagań jakości, raport techniczny.
- **Krok B (bezpieczeństwo):** ✅ **minimalny mechanizm** token→rola gotowy; docelowo SSO (ZP‑002).
- **Krok C (GUI):** ⏭️ **następny** — pełny interfejs webowy na ustabilizowanym API (sekcja 7).

Rdzeń jest kompletny dla wszystkich ekranów łańcucha OPZ — GUI można budować bez dalszych
zależności backendowych w zakresie MVP.

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
