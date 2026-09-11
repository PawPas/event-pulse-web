# 03 — Anti-Corruption Layer: która zależność przecieka i przez ile warstw

> ACL = tłumaczenie reprezentacji z sąsiedniego kontekstu na model domeny **raz, na
> granicy**, zamiast wpuszczania jej w głąb. Szukamy zależności, która przecieka najgłębiej.
> Kryterium sukcesu weryfikowalne grepem (liczba warstw/call-site'ów).

## Kandydaci przecieków

| Przeciek | Skąd | Dokąd przecieka | Miary (grep) |
|---|---|---|---|
| **Reprezentacja tożsamości z tokenu JWT** — `current_user.sub` jako `str`, wymagający `UUID(...)` przy każdym użyciu | kontekst Auth (token, `auth/schemas.py` `TokenPayload.sub: str`) | warstwa danych każdego routera zasobowego | **9 call-site'ów `UUID(current_user.sub)`** w **3 routerach** (analysis, events, reports) |
| **Klasyfikacja `event_type` jako magic string** — „purchase" jako reguła domenowa bez typu | kontekst Ingestii/PRD | logika scoringu | `"purchase"` decyzyjnie w `services/rfm.py:61`; typy eventów zaszyte w generatorze (`events.py`) bez wspólnego enuma |
| Kształt `analysis_result` (dict → JSONB → Pydantic → TS) | rdzeń RFM | DB, API, frontend | ten sam kształt zadeklarowany 3× (opisane w [[../changes/analysis-flow-analysis/research]] D3) |

## Wybór: **reprezentacja tożsamości `UUID(current_user.sub)`**

Najgłębszy i najlepiej mierzalny przeciek: szczegół sąsiedniego kontekstu (fakt, że tożsamość
przychodzi jako **string w claimie `sub` JWT** i wymaga koercji do `UUID`) wsiąkł w **9
miejsc** warstwy dostępu do danych w **3 routerach**. Domena („raport należy do usera") nie
powinna wiedzieć, że user bierze się z tokenu ani że jego id jest stringiem do skonwertowania.

**Dlaczego to korupcja, nie wygoda:**
- Każdy nowy endpoint musi pamiętać o `UUID(...)` — pominięcie = `TypeError`/500 albo, gorzej,
  porównanie string vs UUID, które cicho nie matchuje (potencjalny błąd autoryzacji).
- Zmiana kształtu tożsamości (np. `sub` jako UUID natywnie, albo dodanie tenant-id) wymaga
  ruszenia 9 miejsc.
- Reprezentacja z warstwy transportu (JWT) determinuje kod w warstwie domenowej — odwrotnie
  niż powinno.

## Docelowy ACL (kryterium sukcesu policzalne)

Przetłumaczyć token na **domenowy `UserId` (UUID) raz, na granicy** — w zależności
uwierzytelniającej (`auth/dependencies.py`), tak by `get_current_user` zwracał już
`user_id: UUID`, a nie surowy string do koercji w każdym routerze.

- **Kryterium sukcesu:** `grep -rn "UUID(current_user.sub)" routers/` zwraca **0** po zmianie
  (dziś: 9). Koercja żyje w jednym miejscu na granicy Auth.
- **Spotkanie z [[02-invariant-aggregate-refactor]]:** akcesor agregatu
  `get_owned_report(report_id, current_user)` konsumuje już przetłumaczony `UserId` — obie
  naprawy (niezmiennik własności + ACL tożsamości) zbiegają się w tym samym szwie, co czyni
  je naturalną parą na jeden przyszły cykl.
- **Poza zakresem:** zmiana formatu tokenu, wprowadzenie tenantów, biblioteka autoryzacji.

## Przeciek wtórny (do odnotowania, nie do naprawy teraz)

`event_type == "purchase"` — domenowo istotna klasyfikacja jako goły string. Tani ACL:
enum `EventType` z jawnym `PURCHASE`, tłumaczony przy ingestii. Niski priorytet — jedno
decyzyjne miejsce (`rfm.py:61`), łatwe do znalezienia; korzyść głównie w czytelności i
ochronie przed literówką w typie.
