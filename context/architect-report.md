# Raport architektoniczny — ścieżka 10xArchitect (Moduł 4)

> Sumaryczny two-pager z czterech artefaktów modułu 4. Każde twierdzenie strukturalne
> oparte na artefakcie źródłowym (nie na pamięci o kodzie); liczby weryfikowane grepem.
> Data: 2026-09-11.

## 1. Opisane projekty

Cały moduł wykonano na **jednym repozytorium** — artefakty łańcuchują się jeden w drugi.

| Repo | Stack | Skala | Artefakty |
|---|---|---|---|
| **EventPulse Web** | FastAPI + Python 3.13 (backend) · Vite + React 19 + TS (frontend) · Postgres/Railway · JWT | ~2000 linii kodu produktu, 42 commity, solo autor, MVP domknięte (S-01…S-05) | L2, L3, L4, L5 |

Narzędzia: `ast-grep` niedostępny w środowisku — twierdzenia strukturalne weryfikowane
`grep` (przy tej skali równoważny sygnał; odnotowane w artefaktach).

## 2. Mapa projektu (L2 → `context/map/repo-map.md`)

Kluczowe wnioski:
- **Cztery warstwy backendu bez cykli:** `main.py` → `routers/` → `{auth, models, services, database}`. `services/rfm.py` to czysty rdzeń (tylko stdlib, `list[dict]` in/`dict` out).
- **Strefa ryzyka #1 — przepływ analizy:** background task otwiera sesję **poza DI**
  (`get_session_factory()()`), co już raz ugryzło testy (lessons.md); zmiana pociąga 4 pliki (co-change).
- **God-component frontu:** `ReportDetail.tsx` (504 linie) — upload, generator, run-analysis, polling i tabela w jednym; dotknięty przez 5 z 7 zmian produktowych.
- **Własność danych jako konwencja:** filtr `Report.user_id ==` kopiowany per endpoint; brak mechanizmu wymuszającego.
- **Wrażliwość na środowisko:** `database.py` — jedyne hotfixy produkcyjne w historii (asyncpg URL, `pool_pre_ping`).

## 3. Analiza ficzera (L3 → `context/changes/analysis-flow-analysis/research.md`)

**Badany przepływ:** uruchomienie analizy RFM (`POST /analysis/run` → BackgroundTask →
`compute_rfm` → zapis → `GET /analysis/results`). Wybrany z mapy jako strefa ryzyka #1.
Research prowadzony trzema równoległymi sub-agentami (trace e2e / luki w testach / blast radius).

**Feature overview:** przepływ dwufazowy. Faza HTTP (sesja z DI) waliduje ownership/status/
niepustość i przełącza `status=analyzing`; faza async (BackgroundTask, **nowa sesja poza DI**,
`analysis.py:42`) liczy RFM i zapisuje `analysis_result` (JSONB) + `status=completed`, a na
wyjątku `status=failed`. Frontend pollem czyta status, potem pobiera wynik.

**Technical debt (3 klasy):**
- **D1 (HIGH, Risk #6):** ścieżka awarii istnieje (`analysis.py:74-84`), ale **nietestowana**;
  zagnieżdżony `except` (:83-84) połyka błąd → raport może utknąć w `analyzing`; `GET /results`
  myli „nie uruchomiono" z „padło" (oba 404).
- **D2 (HIGH, Risk #2):** integracja sprawdza tylko zakresy score'ów, nie wartości; przypisanie
  do segmentów pokryte **3 z 6** (potwierdzone grepem: wszystkie 6 jako klucze, ale klienta
  przypisują tylko Champions/Others/Hibernating).
- **D3 (MEDIUM):** kontrakt wyniku zduplikowany 3× (dict → Pydantic → TS); zmiana pola ⇒ 8–12 zmian.

**Twierdzenie potwierdzone narzędziem:** „`test_rfm_algorithm.py` ma 28 testów" (sub-agent)
→ **obalone grepem: 11**. Duplikacja segmentów FE/BE potwierdzona (`SEGMENT_ORDER` w `ReportDetail.tsx:6`).

## 4. Plan refaktoryzacji (L4 → `context/changes/refactor-opportunities/plan.md`)

**Co refaktoryzujemy (opcja O1):** widoczny stan `failed` — `GET /results` przy `status=failed`
zwraca odrębny 409 (zamiast mylącego 404), a ścieżka awarii dostaje test wymuszający wyjątek.
Wybrana z rankingu 4 opcji: jedyna łącząca HIGH-impact ryzyko z wąskim, odwracalnym blast
radiusem i pełną lokalną testowalnością.

**Czego świadomie NIE robimy:** O2 (oracle RFM → test-plan Phase 3), O3 (wspólny kontrakt
typów — odłożone oportunistycznie, do spięcia z najbliższą zmianą kształtu wyniku RFM),
O4 (kolejka/worker — czeka; ryzyko zombie `analyzing` pokryte przez O1), zmian `compute_rfm`.
O3/O4 to dług **zamierzony** (dowód w archiwum: `plan.md` S-05 wybrał BackgroundTasks dla MVP).

**Fazy** (każda = osobny odwracalny commit, od najtańszej):
1. Charakteryzacja ścieżki awarii — test pinuje `status=failed` + obecne 404 (auto: pytest zielony na niezmienionym kodzie; ręczna: monkeypatch celuje w symbol z `analysis.py:15`).
2. Kontrakt `GET /results`: 409 dla failed, 404 zachowane dla created (auto: pełna suita; ręczna: OpenAPI, brak wycieku szczegółów wyjątku).
3. (opcjonalna) UI stanu failed w `ReportDetail` (ręczna weryfikacja ścieżki).

## 5. Domena wg DDD (L5 → `context/domain/`)

**Ubiquitous language — kluczowe rozjazdy model-vs-kod:**
- **Customer / Klient — BRAK w kodzie:** centralny podmiot domeny istnieje wyłącznie jako
  `customer_id: str`, materializowany ulotnie w `compute_rfm`. Sufit domenowy: brak historii klienta.
- **Analysis — brak pamięci:** re-run nadpisuje `analysis_result` (`analysis.py:69`); brak encji przebiegu.
- **`amount==0` dla non-purchase — nieegzekwowane** (grep): niezmiennik PRD tylko na papierze.

**Niezmiennik #1 (najgroźniejszy na 3 osiach):** **izolacja własności danych** — rdzeniowość
HIGH (guardrail bezpieczeństwa), rozsmarowanie HIGH (`UUID(current_user.sub)` w **9 miejscach**,
filtr własności w **7**), egzekwowanie SŁABE (kopiuj-wklej, nie mechanizm).
**Agregat:** Report jest korzeniem (kaskady `Event → Report → User` w `models/report.py:27-51`
to potwierdzają); niezmiennik należy zwinąć do jednego strażnika na granicy agregatu
(`get_owned_report(...)`), redukując 7 filtrów do 1.

**Anti-Corruption Layer:** reprezentacja tożsamości z JWT (`current_user.sub` jako string
wymagający `UUID(...)`) przecieka do **9 call-site'ów w 3 routerach**. ACL: tłumaczyć token
na domenowy `UserId` raz, na granicy Auth. Kryterium sukcesu policzalne: `grep UUID(current_user.sub)`
→ 0 (dziś 9). Naprawa zbiega się z niezmiennikiem #1 w tym samym szwie.

## 6. Decyzje, które należą do mnie

> Sekcja przejrzana punkt po punkcie i **potwierdzona przez autora** (2026-09-11); decyzje
> poniżej są jego własne, nie streszczeniem wyjścia agenta.

- **Cel researchu wybrałem świadomie:** przepływ analizy, bo mapa wskazała go jako strefę
  ryzyka #1, a nie dlatego, że jest największy. AI zaproponowało trzy sub-agenty; ja
  zdecydowałem o granicy (tylko ta ścieżka, bez `compute_rfm` internals).
- **Zróżnicowałem dług zamierzony wg tego, czy jest "tani":** sub-agenci sugerowali kolejkę/
  worker (O4) i wspólny kontrakt typów (O3). **O4 zostaje poza zakresem** — jego jedyne realne
  ryzyko (zombie `analyzing` przy restarcie) pokrywa taniej O1, a plan S-05 jawnie wybrał
  BackgroundTasks „do czasu, aż obciążenie to uzasadni". **O3 świadomie odkładam, ale nie
  bezterminowo** — kontrakt wyniku jest do dziś zamrożony (obszar analizy nietykany od 31.08),
  więc dryf typów nie jest żywym ryzykiem; O3 zrobię przy okazji najblizszej
  zmiany w RFM (np. FR-012b), gdy `openapi-typescript` mozna bedzie latwo dodać
- **Wybór O1 jako „jednej bezpiecznej zmiany" to moja decyzja** oparta na wartość÷ryzyko:
  najwyższy impact przy najwęższym blast radiusie. Kontrpytanie „czy to nie przebudowa
  error-handlingu?" rozstrzygnąłem: nie — ścieżka `failed` już istnieje, zmieniam tylko
  kontrakt odczytu i dokładam testy (guard, nie przebudowa).
- **Weryfikowałem twierdzenia AI, nie przyjmowałem ich na wiarę:** grep obalił „28 testów"
  (realnie 11) i doprecyzował „3/6 segmentów". To zmieniło Technical debt.
- **Niezmiennik własności uznałem za groźniejszy niż poprawność RFM** mimo że oba są HIGH —
  bo RFM jest dobrze odizolowany (1 miejsce), a własność obecna w 16 punktach bez
  strażnika. To ocena ryzyka, nie streszczenie kodu.

---

### Artefakty źródłowe
- L2: `context/map/repo-map.md` (+ `artifact-1-territory.md`, `artifact-2-structure.md`, `artifact-3-contributors.md`)
- L3: `context/changes/analysis-flow-analysis/research.md`
- L4: `context/changes/refactor-opportunities/{research.md, plan.md}`
- L5: `context/domain/{01-domain-distillation.md, 02-invariant-aggregate-refactor.md, 03-anti-corruption-layer.md}`
