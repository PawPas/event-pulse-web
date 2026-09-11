# 01 — Destylacja domeny: ubiquitous language kontra kod

> Domena: RFM customer segmentation (EventPulse Web). Porównanie języka z PRD
> (`context/foundation/prd.md` §Business Logic, §Access Control) z reprezentacją w kodzie.
> Adnotacja „BRAK w kodzie" = pojęcie istnieje w domenie, ale nie ma własnej encji/typu.

## Ubiquitous language — słownik

| Pojęcie (domena) | Definicja z PRD | Reprezentacja w kodzie | Rozjazd model-vs-kod |
|---|---|---|---|
| **Report / Raport** | pojemnik na eventy + wynik analizy, prywatny dla usera | `models/report.py` — encja, aggregate root | ✅ zgodne |
| **Event / Zdarzenie** | `customer_id, timestamp, event_type, amount` | `models/event.py` — encja z FK do Report | ✅ zgodne |
| **Customer / Klient** | **centralny podmiot** — to jego lojalność segmentujemy; persona „chce wiedzieć, kto jest at-risk" | **BRAK w kodzie** — istnieje wyłącznie jako `customer_id: str` w evencie; materializowany ulotnie w `agg: dict` wewnątrz `compute_rfm` (`services/rfm.py:44-65`) i znika po zwróceniu wyniku | 🔴 **duży** — najważniejszy podmiot domeny nie ma encji ani cyklu życia; nie da się go odpytać, śledzić w czasie, ani powiązać między raportami |
| **Segment** | zamknięty zbiór 6: Champions, Loyal Customers, Potential Loyalists, At Risk, Hibernating, Others | lista lambd `_SEGMENT_RULES` (`services/rfm.py:7-14`) + string-label w wyniku; **zduplikowany** jako `SEGMENT_ORDER` we froncie (`ReportDetail.tsx:6`) | 🟠 rozjazd — brak typu/enum; reguły i kolejność żyją w dwóch językach bez wspólnego źródła |
| **RFM Score (R/F/M)** | ranga 1–5 per klient per wymiar | pola w dict `customers[]` wewnątrz `analysis_result` (JSONB) | 🟠 rozjazd — score istnieje tylko w blobie JSON, nie jest zapytywalny ani indeksowalny |
| **Analysis / Analiza** | **akcja** produkująca wgląd; „uruchom analizę", „uruchom ponownie po dodaniu eventów" (FR-010/011) | nie ma encji Analysis — jest przejście `ReportStatus` + blob `analysis_result`; **re-run nadpisuje** poprzedni wynik (`analysis.py:69`) | 🔴 rozjazd — analiza jako zdarzenie w czasie nie istnieje; brak historii przebiegów, „re-run" gubi poprzedni wynik bez śladu |
| **Purchase / Zakup** | tylko `event_type == "purchase"` zasila wymiar Monetary; pozostałe typy tylko Frequency | goły string `"purchase"` w porównaniu (`services/rfm.py:61`) + zaszyty w generatorze próbek | 🟠 rozjazd — domenowo istotna klasyfikacja jako magic string bez typu (patrz [[03-anti-corruption-layer]]) |
| **Recency / Frequency / Monetary** | trzy wymiary scoringu | zmienne lokalne w `compute_rfm` | ✅ zgodne (choć nienazwane jako typy) |
| **Quintile / Kwintyl** | granice rang z populacji raportu, nie progi stałe | `_cutpoints` → `statistics.quantiles(n=5)` (`services/rfm.py:23-27`) | ✅ zgodne |

## Rozjazdy, które zaskakują (top 3)

1. **Customer nie istnieje jako byt.** Cała wartość produktu to „powiedz mi coś o moich
   klientach", a klient jest w kodzie efemeryczną nazwą-kluczem. To nie błąd MVP — to
   świadoma prostota — ale definiuje sufit domenowy: dopóki Customer nie jest bytem,
   niemożliwe są historia klienta, śledzenie migracji między segmentami, cross-report.
2. **Analiza nie ma pamięci.** Re-run (FR-011) nadpisuje `analysis_result`. Domena mówi
   o „ponownym uruchomieniu", co sugeruje serię przebiegów; kod trzyma tylko ostatni.
3. **`amount == 0` dla non-purchase nie jest egzekwowane.** PRD: „amount must be 0 for
   non-purchase events". Kod nie sprawdza tego przy ingestii (grep: brak walidacji) —
   niezmiennik domenowy istnieje tylko na papierze (patrz [[02-invariant-aggregate-refactor]]).

## Materiał wejściowy dla ranking/roadmap

Rdzeniowe subdomeny: **Segmentacja RFM** (rdzeń wartości, dobrze odizolowany w
`services/rfm.py`) i **Tożsamość/własność danych** (guardrail bezpieczeństwa, rozsmarowany —
patrz [[02-invariant-aggregate-refactor]]). Pojęcia z „BRAK w kodzie" (Customer, Analysis
jako zdarzenie) to kandydaci na przyszłe encje, gdy produkt wyjdzie poza jednorazowy
batch — nie teraz.
