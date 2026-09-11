# Artifact 1 — Territory: gdzie projekt żyje (historia gita)

> Zakres: pełna historia repo (2026-07-15 → 2026-09-11, 42 commity).
> Odfiltrowano szum: lockfile'y (`uv.lock`, `package-lock.json`), `context/materials/`, `.claude/`.

## Rytm projektu

| Okres | Commity | Co się działo |
|---|---|---|
| 2026-07-15 → 07-19 | 7 | bootstrap: scaffold FastAPI + Vite, foundation docs, deploy na Railway |
| 2026-07-20 | 17 | **szczyt aktywności**: auth-scaffold, db-schema-baseline, auth-flows, report-management, event-file-upload — pięć zmian w jeden dzień |
| 2026-07-21 → 07-24 | 9 | sample-generator, rfm-analysis-dashboard (backend p1–p2) |
| 2026-08-31 | 6 | domknięcie dashboardu (frontend p3), impl-review fixes, archiwizacja — po 5-tygodniowej przerwie |
| 2026-09-08 → 09-11 | 3 | sync toolkitu, PATCH raportów, README + test-plan |

Wniosek: projekt budowany krótkimi, gęstymi seriami wokół change-idów z `context/changes/`; między seriami tygodnie ciszy. Historia jest niemal 1:1 mapowalna na roadmapę (F-01…S-05).

## Najczęściej dotykane pliki (kod produktu)

| Plik | Zmiany | Dlaczego gorący |
|---|---|---|
| `main.py` | 7 | punkt rejestracji każdego nowego routera — rośnie z każdą zmianą |
| `frontend/src/pages/ReportDetail.tsx` | 5 | **hub frontendu**: upload, generator, run-analysis i dashboard wszystkie lądują na tej jednej stronie |
| `tests/conftest.py` | 5 | infrastruktura testowa dostrajana przy każdej zmianie backendu (w tym pre-inject engine dla background tasks) |
| `database.py` | 5 | engine, sesje, health check — w tym **hotfix produkcyjny** `pool_pre_ping` (commit `1ff78dc`) poza cyklem change-idów |
| `frontend/src/api/client.ts` | 4 | pojedynczy klient HTTP — co-change z każdym nowym endpointem |
| `routers/events.py` | 4 | upload + sample generator + poprawki z impl-review |

## Wzorce co-change (co zmienia się razem)

- **`routers/analysis.py` + `services/rfm.py` + `models/report.py` + `database.py`** — rdzeń analizy; zmiana w przepływie analizy pociąga wszystkie cztery (commity `559dccf`, `81849b6`, `2f1d4a3`).
- **`ReportDetail.tsx` + `client.ts` + `types/report.ts`** — każdy nowy endpoint backendu odbija się w tej trójce (commity `48937c2`, `b946029`, `7159602`).
- **`main.py` + nowy router** — stały rytuał rejestracji.
- **każdy feature backendu + `tests/conftest.py`** — sygnał, że fixture'y są wrażliwe na kształt aplikacji.

## Aktywność × obszary wrażliwe

- **Runtime/dane**: `database.py` dostał jedyny w historii hotfix "fix:" poza cyklem zmian (stale asyncpg connections na Railway) — najbardziej produkcyjnie wrażliwy plik repo.
- **Auth**: `auth/` zmieniany tylko w dwóch seriach (scaffold + flows), od tego czasu stabilny — dojrzały, ale każdy nowy router od niego zależy.
- **Publiczne API**: `routers/` rośnie addytywnie; wzorce (ownership filter, Pydantic response) kopiowane między plikami — ryzyko dryfu przy kopiowaniu.

## Szum odfiltrowany

`uv.lock`, `package-lock.json`, `context/materials/` (materiały kursu), `.claude/` (toolkit), commity `chore(toolkit)`.
