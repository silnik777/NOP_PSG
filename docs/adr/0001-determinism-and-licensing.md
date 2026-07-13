# ADR 0001 — Determinizm obliczeń i polityka licencyjna

Status: Zaakceptowany · Data: 2026-07-13 · Kontekst: Faza I (rdzeń)

## Kontekst

Specyfikacja e-GSD (§9.1 Poziom B) wymaga, aby wyniki flagowych projektów historycznych
nie zmieniły się o więcej niż 0,001% między wdrożeniami. Jednocześnie W11.2 dopuszcza
wyłącznie biblioteki na licencjach permissive (MIT/Apache/BSD), zakazując kopyleftu (GPL/AGPL).

## Decyzja

1. **Determinizm zmiennoprzecinkowy:**
   - Wszystkie zależności obliczeniowe są **przypięte do dokładnych wersji** (`pyproject.toml`).
     Kluczowe: `CoolProp==8.0.0`, `scipy==1.13.1`, `numpy==1.26.4`.
   - Silnik gazowy jest **bezstanowy** i **jednowątkowy per żądanie**; nie stosujemy
     niedeterministycznych redukcji równoległych w ścieżce obliczeniowej.
   - Solvery numeryczne (Brent) mają jawnie ustaloną tolerancję i przedziały startowe.
   - Każdy `ResultRecord` przechowuje `engine_version` oraz **hash SHA-256** wejść i wersji
     modeli — regresja jest wykrywalna deterministycznie.

2. **Model termodynamiczny:**
   - Silnik używa backendu **CoolProp `HEOS`** (wielopłynowy model Helmholtza), który dla
     składników gazu ziemnego i wodoru wykorzystuje **binarne parametry i funkcje odejścia
     GERG-2008 (ISO 20765-1)**. Dedykowany backend `GERG2008` nie jest skompilowany w oficjalnym
     wheelu CoolProp 8.0.0; przy dostarczeniu buildu z tym backendem można go włączyć bez zmian
     w warstwie domenowej (adapter jest wymienny).
   - Wartość `engine_version` jednoznacznie identyfikuje model i wersję biblioteki.

3. **Licencje:** CoolProp (MIT), SciPy/NumPy (BSD), FastAPI/SQLAlchemy/Pydantic (MIT/BSD),
   PostgreSQL (PostgreSQL License — permissive). SBOM generowany w CI (CycloneDX) do kontroli
   braku licencji kopyleftowych. **REFPROP** (komercyjny) używany jest wyłącznie jako *oracle*
   walidacyjny poza runtime aplikacji (decyzja Zamawiającego #3), nie jest zależnością produkcyjną.

## Konsekwencje / uwaga walidacyjna

Referencyjne wartości liczbowe podane w OPZ (np. TV-M1-001: 1245,5 kW / 354,2 K) **nie są
zgodne** z wynikami rzeczywistego modelu real-fluid dla podanych danych wejściowych (silnik
zwraca ~2281 kW / ~376 K; niezależny szacunek gazu doskonałego potwierdza spręż izentropowy
~183 kJ/kg, zgodny z silnikiem). Zgodnie z zasadą „wartości referencyjne muszą pochodzić ze
zwalidowanego źródła" test TV-M1-001 **dokumentuje tę rozbieżność** (xfail) i wskazuje na
konieczność rozstrzygnięcia z oracle REFPROP przed formalnym odbiorem Modułu I.
