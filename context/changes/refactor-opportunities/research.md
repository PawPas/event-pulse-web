# Research — Refactor Opportunities (M4L4, Element ④)

> Wejście: `context/changes/analysis-flow-analysis/research.md` (D1/D2/D3).
> Ten dokument porządkuje dług w **rankowane opcje refaktoru z trade-offami** i kończy
> rekomendacją. Decyzja, co realizujemy, zapada w sekcji „Decyzja" (moja, nie agenta).
> Eksploracja — bez refaktoru.

## Kandydaci (z długu D1–D3)

| ID | Kandydat | Docelowy kształt | Ryzyko dziś | Blast radius | Intencjonalność (dowód) |
|----|----------|------------------|-------------|--------------|--------------------------|
| O1 | **Widoczny stan `failed`** — odróżnić „nie uruchomiono" od „analiza padła" w `GET /results` + przybić ścieżkę awarii testem | `GET /results` przy `status=failed` zwraca odrębny kod (np. 409/422 z detalem „Analysis failed"), a `_run_analysis` ma test wymuszający wyjątek → `status=failed` utrwalony | HIGH (Risk #6) — user utyka na „Analyzing…", brak sygnału błędu | Wąski: `routers/analysis.py` (kontrakt błędu) + `tests/test_analysis.py`; opcjonalnie `ReportDetail.tsx` (UI) | Niezamierzony: `impl-review-phase-3.md` flagował objaw; obecny 404 conflates dwa stany (`analysis.py:152-156`) |
| O2 | **Domknięcie oracle RFM** — testy dokładnych wartości + przypisania do wszystkich 6 segmentów + granica priorytetu reguł | fixture'y z niezależnie policzonymi wartościami wg PRD §Business Logic; po 1 kliencie na każdy segment; przypadek R=3,F=4,M=4 | HIGH (Risk #2) — cicha degradacja jakości analizy | Wąski, tylko testy: `tests/test_rfm_algorithm.py`, `tests/test_analysis.py` | Niezamierzony: fixture pokrywa przypisaniem 3/6 segmentów (weryfikacja grep, M4L3) |
| O3 | **Wspólne źródło kontraktu wyniku** — usunąć ręczną duplikację kształtu RFM backend↔frontend | generacja typów TS z Pydantic (np. openapi-typescript) lub współdzielony schemat; jedno źródło segmentów | MEDIUM — dryf typów int/float, rozjazd listy segmentów | **Szeroki**: `rfm.py`, `analysis.py`, `types/report.ts`, `ReportDetail.tsx`, build frontu, testy; nowa zależność narzędziowa | Zamierzony (świadomy trade-off MVP): SPA display-only, kontrakt mały; duplikacja była tańsza niż tooling na starcie |
| O4 | **Trwałość zadań analizy** — kolejka/worker zamiast BackgroundTasks, ochrona przed zombie `analyzing` przy restarcie | Redis/worker + idempotencja + timeout | MEDIUM/LOW — realne wolumeny małe, 30s NFR spełniony BackgroundTasks | Bardzo szeroki: infra, deploy, `analysis.py`, testy | Zamierzony: `plan.md` S-05 jawnie wybrał BackgroundTasks dla MVP; worker „promoted later if load justifies" |

## Werdykty intencjonalności

- **O1, O2** — dług **niezamierzony**: luki, nie decyzje. Oba mają twardy dowód (review,
  grep). Najlepsi kandydaci do naprawy.
- **O3, O4** — dług **zamierzony**: świadome trade-offy MVP z dowodem w archiwum
  (`plan.md` S-05, tech-stack.md). Naprawiać dopiero gdy zmieni się skala/wymagania —
  nie teraz.

## Ranking (wartość ÷ ryzyko zmiany)

1. **⭐ O1** — najwyższe ryzyko produktowe (HIGH, user-widoczne), najwęższy blast radius,
   w pełni testowalny lokalnie przez wstrzyknięcie awarii. Jedna bezpieczna zmiana.
2. **O2** — równie wysokie ryzyko, ale to naturalnie materiał fazy testowej
   (`test-plan.md` Phase 3), nie refaktoru kodu produktu; brak zmiany zachowania.
3. **O3** — realny dług (cichy dryf typów FE/BE, brak testów komponentu), ale kontrakt jest
   dziś **zamrożony** (obszar analizy nietykany od 31.08), więc ryzyko nie jest żywe. Nie
   osobny cykl teraz — **oportunistycznie przy najbliższej zmianie kształtu wyniku RFM**
   (np. FR-012b), gdy `openapi-typescript` staje się tanim dokładem do i tak otwartego pliku.
4. **O4** — najniższy priorytet; czeka. Jedyne realne ryzyko (zombie `analyzing` przy
   restarcie) pokrywa taniej O1; resztę przenieś do observability/skalowania.

## Decyzja (moja — nie agenta)

Realizujemy **O1**. Uzasadnienie: jedyny kandydat łączący HIGH-impact ryzyko z wąskim,
odwracalnym blast radiusem i pełną lokalną testowalnością — modelowa „jedna bezpieczna
zmiana" na tę ścieżkę. Kontrpytanie do ⭐: „czy to nie jest przebudowa error-handlingu?"
— nie; ścieżka `failed` **już istnieje** (`analysis.py:74-84`), zmieniamy tylko *kontrakt
odczytu* (kod błędu w `GET /results`) i *dokładamy testy* na istniejące zachowanie. To guard,
nie przebudowa.

**Czego świadomie NIE robimy w tej zmianie:** O2 (→ test-plan Phase 3), O3 (osobny cykl),
O4 (observability), zmian w kolejkowaniu BackgroundTasks, zmian algorytmu `compute_rfm`,
przebudowy UI poza minimalnym rozróżnieniem stanu `failed`.
