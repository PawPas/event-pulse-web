# EventPulse Web – MVP

## Główny problem

Małe i średnie firmy e-commerce, SaaS oraz zespoły produktowe zbierają duże ilości danych o zachowaniu klientów (zdarzenia typu przeglądanie produktu, dodanie do koszyka, zakup, logowanie itp.), ale mają trudność z szybkim przekształceniem tych danych w praktyczne wnioski biznesowe.

Ręczne analizowanie zdarzeń w arkuszach kalkulacyjnych lub prostych narzędziach jest czasochłonne. Zaawansowane platformy analityczne są często zbyt drogie lub zbyt skomplikowane na potrzeby mniejszych zespołów. Brakuje prostego rozwiązania, które pozwoliłoby szybko uzyskać klasyczną, biznesowo użyteczną analizę klientów — przede wszystkim segmentację na podstawie ich aktywności i wartości.

## Najmniejszy zestaw funkcjonalności

- Prosty system kont użytkowników (rejestracja i logowanie).
- Tworzenie, przeglądanie, edycja i usuwanie **Raportów**.
- Dodawanie danych o zdarzeniach klientów (eventów) przez:
  - Upload pliku (CSV, JSON lub podobny)
  - Wklejenie danych bezpośrednio w interfejsie
  - Wbudowany generator przykładowych danych (do szybkiego testowania)
- Przeglądanie zaimportowanych zdarzeń klientów (lista z podstawowymi możliwościami filtrowania).
- Automatyczna analiza danych zdarzeń klientów:
  - Obliczanie wskaźników RFM (Recency – aktualność, Frequency – częstotliwość, Monetary – wartość monetarna)
  - Segmentacja klientów na grupy biznesowe (np. Champions, Loyal Customers, At Risk, Hibernating i inne)
  - Podstawowe agregacje i podsumowania (liczba klientów, średnia wartość, rozkład segmentów)
- **Dashboard / widok raportu** pokazujący:
  - Kluczowe metryki (liczba zdarzeń, liczba unikalnych klientów, procent klientów w poszczególnych segmentach)
  - Rozkład klientów według segmentów (z wizualizacjami)
  - Najważniejsze wnioski biznesowe (np. udział klientów wymagających uwagi)
  - Tabelę z wynikami segmentacji klientów (z możliwością sortowania i filtrowania)
- Możliwość ponownego uruchomienia analizy na istniejącym raporcie (np. po dodaniu nowych zdarzeń klientów).

## Co NIE wchodzi w zakres MVP

- Analiza w czasie rzeczywistym.
- Inne typy analiz poza segmentacją RFM (np. analiza lejka, kohorty, modelowanie predykcyjne).
- Zaawansowane i interaktywne wizualizacje danych.
- Eksport wyników raportu do plików (PDF, Excel itp.).
- Automatyczne planowanie i cykliczne uruchamianie analiz.
- Współdzielenie raportów i współpraca zespołowa.
- Integracje z zewnętrznymi systemami i źródłami danych.
- Zaawansowane funkcje sztucznej inteligencji (poza ewentualnym prostym podsumowaniem wyników).
- Obsługa bardzo dużych zbiorów danych (powyżej kilkuset tysięcy–miliona zdarzeń w jednym raporcie).
- System powiadomień i alertów.
- Aplikacja mobilna.

## Kryteria sukcesu

- Użytkownik może założyć konto, dodać dane o zdarzeniach klientów i uzyskać gotową analizę segmentacji w ciągu kilku minut.
- System poprawnie oblicza wskaźniki RFM i przypisuje klientom sensowne, biznesowo zrozumiałe segmenty.
- Dashboard i wyniki raportu pomagają szybko zidentyfikować grupy klientów wymagające szczególnej uwagi (np. klienci w segmencie „At Risk”).
- Ponowne uruchomienie analizy po dodaniu nowych danych działa niezawodnie i w rozsądnym czasie.
- Projekt spełnia wymagania techniczne stawiane minimalnym produktom w ramach certyfikacji (pełny CRUD na kluczowych encjach, istotna logika biznesowa, testy pokrywające zdefiniowane ryzyka, autoryzacja użytkownika oraz kompletna dokumentacja).
