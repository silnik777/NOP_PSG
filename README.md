# e-GSD — zwalidowany rdzeń (walking skeleton)

Webowa platforma wspomagania decyzji strategicznych i oceny projektów B&R dla operatora
systemu dystrybucyjnego gazu (OSD). Ten przyrost dostarcza **matematycznie zweryfikowany
rdzeń** (nie makietę): centralny silnik właściwości gazów (GERG-2008 przez CoolProp),
Moduł I (sprężanie) oraz model danych Projekt/Wariant/Wynik z audytem.

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
- `POST /api/v1/projects` / `GET /api/v1/projects/{id}` — projekty i warianty (skrót).

## Ważna uwaga walidacyjna

Wartości referencyjne z OPZ dla sprężania (TV-M1-001) okazały się niezgodne z modelem
real-fluid — patrz `docs/adr/0001-determinism-and-licensing.md` i `tests/integration/test_tv_m1_001.py`.
