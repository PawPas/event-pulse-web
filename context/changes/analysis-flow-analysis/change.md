---
change_id: analysis-flow-analysis
title: Analiza przepływu uruchomienia analizy RFM (M4L3 — deep focus)
status: new
created: 2026-09-11
updated: 2026-09-11
archived_at: null
---

## Notes

Analiza przepływu uruchomienia analizy RFM: od POST /api/reports/{id}/analysis/run, przez BackgroundTasks i compute_rfm, po zapis wyniku i odczyt GET /analysis/results. Cel wybrany z context/map/repo-map.md (strefa ryzyka #1: sesja poza DI, coupling 4 plików). Wyłącznie analiza stanu obecnego — bez refaktoru.
