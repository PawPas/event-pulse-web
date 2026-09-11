# Artifact 3 — Contributors: kto wie co (obszar: przepływ analizy RFM)

> Obszar wybrany na podstawie artefaktów 1–2: **przepływ analizy** (`routers/analysis.py`,
> `services/rfm.py`, `models/report.py`, `database.py`) — centralny biznesowo i jedyny
> łamiący wzorzec DI.

## Autorzy

Repo jest **solo**: 42/42 commity od Pawła Paskudzkiego (dwie tożsamości e-mail — ta sama osoba).
Klasyczna mapa „kogo zapytać" nie istnieje; wiedza jest w 100% skupiona w jednej głowie.
**Proxy wiedzy kontrybutorów są artefakty w `context/`** — każda zmiana ma folder z change.md,
planem i raportami z review, które pełnią rolę „PR-ów do przeczytania przed zmianą".

## Historia wybranego obszaru (12 miesięcy = całe życie repo)

| Commit | Data | Temat |
|---|---|---|
| `70af186` | 07-19 | async engine + health check (db-schema-baseline p1) |
| `0446490` | 07-20 | modele ORM (p2) |
| `10a4489` | 07-20 | **fix**: `postgresql://` → `postgresql+asyncpg://` dla Railway `DATABASE_URL` |
| `1ff78dc` | 07-20 | **fix**: `pool_pre_ping` na stale asyncpg connections |
| `559dccf` | 07-23 | migracja DB + serwis RFM (rfm-analysis-dashboard p1) |
| `81849b6` | 07-24 | endpointy analizy + testy integracyjne (p2) |
| `2f1d4a3` | 08-31 | poprawki z impl-review |

Powtarzający się temat: **integracja z Railway Postgres** — dwa hotfixy „fix:" tego samego dnia,
oba poza cyklem change-idów. To jedyne miejsce w historii, gdzie coś zaskoczyło na produkcji.

## Co przeczytać przed zmianą w tym obszarze („PR-y i decyzje")

1. `context/archive/2026-07-22-rfm-analysis-dashboard/plan.md` — decyzja o BackgroundTasks
   (zamiast workera/kolejki) i kontrakt statusów `created → analyzing → completed/failed`.
2. `context/archive/2026-07-22-rfm-analysis-dashboard/reviews/impl-review-phase-*.md` — co
   wyszło w review trzech faz (triage poprawek w `2f1d4a3`).
3. `context/foundation/lessons.md` — „Pre-inject test engine when background tasks bypass
   FastAPI DI" — edge case testowy tego obszaru; bez tej wiedzy testy analizy wyglądają
   na „pustą bazę".
4. `context/archive/2026-07-20-event-file-upload/plan.md` — kontrakt walidacji wejścia
   (cap 200k, odrzucenie przed zapisem) — analiza konsumuje dane, które ten kontrakt wpuścił.

## Rozproszenie wiedzy — werdykt

Wiedza **skupiona** (jedna osoba + artefakty `context/`). Ryzyko busa = 1. Mitygacja
istniejąca: dyscyplina artefaktów (plan/review/lessons per zmiana) jest na tyle konsekwentna,
że nowy kontrybutor (człowiek albo agent) może odtworzyć intencje z samego repo — to
świadoma strategia projektu (patrz `AGENTS.md`, `CLAUDE.md`).
