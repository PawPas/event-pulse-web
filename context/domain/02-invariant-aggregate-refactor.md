# 02 — Niezmiennik #1 i agregat, do którego należy

> Wybór najgroźniejszego niezmiennika oceniony na trzech osiach: **rdzeniowość**
> (jak bardzo dotyka sedna wartości/bezpieczeństwa), **rozsmarowanie** (w ilu miejscach
> jest wymuszany) i **egzekwowanie** (mechanizm czy konwencja). Liczby zweryfikowane grepem.

## Kandydaci

| Niezmiennik | Rdzeniowość | Rozsmarowanie | Egzekwowanie | Groźność |
|---|---|---|---|---|
| **Izolacja własności** — user widzi wyłącznie własne raporty i eventy | HIGH (guardrail bezpieczeństwa, PRD §Access Control „no user's data accessible to another account") | **HIGH** — `UUID(current_user.sub)` w **9 miejscach** (analysis.py, events.py, reports.py), filtr `Report.user_id ==` w **7** | **SŁABE** — kopiuj-wklej w każdym endpoincie, brak wspólnego strażnika | 🔴 **najwyższa** |
| Monetary tylko z purchase | HIGH (poprawność RFM) | LOW — 1 miejsce (`rfm.py:61`) | OK — scentralizowane w `compute_rfm` | 🟢 niska (dobrze zamknięty) |
| Każdy klient w dokładnie jednym segmencie | HIGH | LOW — `rfm.py:7-14` z Others jako catch-all | OK — first-match + fallback | 🟢 niska |
| `amount == 0` dla non-purchase | MEDIUM | — | **BRAK** — nieegzekwowane (grep) | 🟠 średnia, ale niski impact (monetary i tak sumuje tylko purchase) |

## Niezmiennik #1 (wybór): **Izolacja własności danych**

> „Żaden użytkownik nie ma dostępu do raportu ani eventów należących do innego konta —
> na żadnej ścieżce odczytu ani zapisu."

Najgroźniejszy, bo łączy **najwyższą rdzeniowość** (naruszenie = wyciek danych, złamanie
guardraila PRD) z **najszerszym rozsmarowaniem** (16 punktów egzekwowania) i **najsłabszym
egzekwowaniem** (konwencja, nie mechanizm). Nowy endpoint zasobowy, który zapomni dopisać
`Report.user_id == UUID(current_user.sub)`, przejdzie testy jednostkowe własnej ścieżki i
wycieknie dane — nic go nie zatrzyma. To dokładnie ryzyko #1 z `test-plan.md` i strefa
ryzyka #5 z `context/map/repo-map.md`.

## Agregat, do którego należy

**Report jest korzeniem agregatu (aggregate root).** Dowód z modelu:
- `Event` ma FK do `Report` z `ondelete="CASCADE"` i relacją `cascade="all, delete-orphan"`
  (`models/report.py:49-51`) — Event nie ma niezależnego cyklu życia; istnieje wyłącznie
  w kontekście swojego Reportu.
- `Report` ma FK do `User` z `ondelete="CASCADE"` (`models/report.py:27-29`) — Report należy
  do dokładnie jednego Usera.

Granica agregatu: **User → Report → Events**. Cały dostęp do Events powinien przechodzić
przez ich Report, a dostęp do Reportu — przez sprawdzenie właściciela. Dziś ta granica
istnieje w modelu danych (kaskady), ale **nie jest strażnikiem dostępu** — każdy router
odtwarza ją ręcznie w zapytaniu.

## Docelowy kształt (guard, nie przebudowa)

Przekuć niezmiennik z konwencji w **jeden punkt egzekwowania na granicy agregatu**:
zależność/akcesor `get_owned_report(report_id, current_user) -> Report`, która zwraca raport
tylko gdy należy do usera (inaczej 404), i przez którą przechodzą wszystkie endpointy
raportowe i eventowe. 16 rozsianych warunków zwija się do jednego; nowy endpoint, który
użyje akcesora, dziedziczy niezmiennik za darmo; który go pominie — jest widoczny w review.

- **Charakteryzacja przed zmianą:** najpierw macierz testów izolacji dla *każdego* endpointu
  (to jest `test-plan.md` Phase 1 „Isolation matrix completion") — przybija obecne
  zachowanie, zanim ruszymy strukturę.
- **Kryterium sukcesu:** liczba miejsc konstruujących filtr własności spada z 7 do 1;
  macierz izolacji (dwóch userów × wszystkie endpointy) zielona przed i po.
- **Poza zakresem:** zmiana modelu danych, wprowadzanie encji Customer, RBAC.

Zależność, która przecieka przez tę samą granicę (`UUID(current_user.sub)`), opisana w
[[03-anti-corruption-layer]] — obie naprawy naturalnie spotykają się w akcesorze agregatu.
