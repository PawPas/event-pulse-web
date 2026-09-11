# Plan — Widoczny stan `failed` dla przepływu analizy RFM (O1)

> Zmiana wybrana w `research.md` (Element ④, decyzja: O1). Cel: awaria analizy przestaje
> być „niema" — ścieżka `failed` jest przybita testem, a klient odpytujący `GET /results`
> dostaje sygnał odróżnialny od „jeszcze nie uruchomiono".
>
> Zakres celowo wąski. Poza zakresem: O2 (oracle RFM → test-plan Phase 3), O3 (wspólny
> kontrakt typów), O4 (kolejka/worker), zmiany `compute_rfm`, przebudowa UI ponad minimum.

## Kontekst z researchu

- Ścieżka awarii **istnieje** (`routers/analysis.py:74-84`): wyjątek → rollback →
  `status = failed` → commit. **Nietestowana** (Risk #6).
- `GET /results` (`analysis.py:152-156`) zwraca **404 „run analysis first"** zarówno gdy
  analizy nie uruchomiono, jak i gdy padła (bo `analysis_result` pozostaje `None`). Klient
  nie odróżni tych stanów.
- Frontend główny sygnał statusu bierze z pollingu `GET /{id}`; `GET /results` to ścieżka
  wtórna, ale myląca.

## Docelowy kształt

1. `GET /results` przy `report.status == failed` zwraca **409 Conflict** z detalem
   „Analysis failed — please re-run", zamiast mylącego 404. (Alternatywa rozważona: 422;
   wybrano 409 jako „stan zasobu koliduje z żądaniem" — analiza jest w stanie terminalnym
   `failed`.) 404 „run analysis first" zostaje wyłącznie dla stanu `created` bez wyniku.
2. Ścieżka awarii ma test wymuszający wyjątek w `compute_rfm` (monkeypatch) i sprawdzający,
   że `status=failed` faktycznie się utrwala.

## Fazy (każda = osobny, odwracalny commit; od najtańszej i najbardziej samodzielnej)

### Faza 1 — Charakteryzacja ścieżki awarii (test-only, pins current behavior)
Przed dotknięciem kodu produktu przybijamy **obecne** zachowanie niepokrytej ścieżki.
- Nowy test w `tests/test_analysis.py`: `monkeypatch` na `routers.analysis.compute_rfm`,
  by rzucał `ValueError`; uruchom `POST /analysis/run`; po zakończeniu background taska
  asertuj przez `GET /{id}`, że `status == "failed"`.
- Drugi asert **pinuje obecny kontrakt**: `GET /results` w tym stanie zwraca dziś **404**.
- **Weryfikacja auto:** `uv run pytest tests/test_analysis.py -k failed` — zielono na
  niezmienionym kodzie produktu (dowód, że test opisuje stan obecny, nie życzeniowy).
- **Weryfikacja ręczna:** przejrzyj, czy monkeypatch celuje w symbol użyty przez
  `_run_analysis` (import w `analysis.py:15`), a nie w `services.rfm` bezpośrednio.

### Faza 2 — Odróżnialny kontrakt `GET /results` dla stanu `failed` (kod + test)
- W `get_analysis_results` (`analysis.py:152-`) dodać gałąź: jeśli `status == failed` →
  `HTTPException(409, "Analysis failed — please re-run")` **przed** sprawdzeniem
  `analysis_result is None`.
- Zaktualizować test charakteryzacyjny z Fazy 1: oczekiwany kod z 404 → **409** (to jest
  moment, w którym zmiana zachowania staje się jawna w diffie testu).
- Dodać test, że stan `created`-bez-wyniku **nadal** zwraca 404 „run analysis first"
  (ochrona przed regresją rozróżnienia).
- **Weryfikacja auto:** pełna `uv run pytest` — zielono (66+ testów).
- **Weryfikacja ręczna:** OpenAPI `/docs` pokazuje 409 jako możliwą odpowiedź; detale
  błędów nie wyciekają wewnętrznych szczegółów wyjątku.

### Faza 3 — (opcjonalna) UI stanu `failed` w ReportDetail
- `ReportDetail.tsx`: gdy poll zwróci `status == "failed"`, pokazać komunikat + akcję
  „Uruchom ponownie" zamiast wiecznego „Analyzing…".
- **Weryfikacja auto:** `cd frontend && npm run lint` + `npm test` (jeśli dojdzie test
  komponentu — inaczej pominąć).
- **Weryfikacja ręczna:** wymuś awarię lokalnie (tymczasowy raise w `compute_rfm`), przejdź
  ścieżką w UI, potwierdź komunikat i działające ponowne uruchomienie.
- **Uwaga:** ta faza to szew do frontendu; jeśli traktujemy zmianę jako czysto backendową,
  Faza 3 zostaje jako ręczna pozycja checklisty, nie kod.

## Kryteria sukcesu (całość)
- Wymuszona awaria analizy → raport w `status=failed` (nie zombie `analyzing`).
- `GET /results`: 409 dla `failed`, 404 dla `created`-bez-wyniku, 200 dla `completed` —
  trzy stany rozróżnialne.
- Zero regresji: pełna suita backendu zielona; lint frontu zielony.
- Mechanizmy (testy) zielone; żadne wymuszanie nie jest włączane niejawnie.

## Progress
- [ ] 1. Charakteryzacja ścieżki awarii — test wymuszający wyjątek, pinuje status=failed + obecne 404
- [ ] 2. Kontrakt GET /results: 409 dla failed, 404 zachowane dla created; testy zaktualizowane
- [ ] 3. (opcjonalna) UI stanu failed w ReportDetail + weryfikacja ręczna

## Uwaga o realizacji
Implementacja (`/10x-implement refactor-opportunities phase 1`) jest poza zakresem ścieżki
10xArchitect M4L4 — artefaktem lekcji jest **ten plan**. Fazy dokładamy znanym cyklem z
M2/M3, jeśli chcemy domknąć zmianę w repo.
