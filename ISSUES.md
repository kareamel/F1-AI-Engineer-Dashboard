# Issues & Fix List

Things noticed while learning the codebase. Not fixed yet — interview prep comes first.

**Status:** `open` · `in progress` · `fixed`
**Type:** `verified` = seen directly in the code · `inferred` = what the code suggests would happen, not seen happening

---

## Code

| # | Status | Where | Issue | Type | Fix idea |
|---|---|---|---|---|---|
| 1 | open | `src/server.py:211-218` | Placeholder fields `car_ahead_driver`, `car_ahead_gap`, `car_ahead_gap_prev`, `car_behind_driver`, `car_behind_gap`, `car_behind_gap_prev`, `leader_driver`, `leader_gap` are always `None` and the dashboard never reads them. | verified | Remove them, or fill them from `all_cars` (car at position − 1, car at position 1). |
| 2 | open | `src/server.py:207-210` → `dashboard/index.html:1185-1194` | `exit_position` is always `None` (dashboard shows "P–"); `free_air` is always `True` and `traffic_driver` always `None` (dashboard always shows free air). | verified | `exit_position` ← `pit_rejoin_position`; compute free air / traffic from gap to car ahead. |
| 3 | open | `src/server.py:577` | `_build_payload()` is not inside a `try`. If it ever raised an error, `asyncio.gather` would stop the whole server. | inferred | Wrap in `try/except`, log the error, skip that tick. |
| 4 | open | `src/server.py:584` | `except (ConnectionClosed, Exception)` catches every error, so a real bug in sending would be hidden and the tab silently dropped. | verified | Catch `ConnectionClosed` only, or log other exceptions. |

## Docs & setup

| # | Status | Where | Issue | Fix idea |
|---|---|---|---|---|
| 5 | open | `src/server.py:7` | Docstring says "calls Claude API" — the code calls Gemini. Also mentions `ENGINEER_CYCLE_SECONDS`, which doesn't exist. | Update the docstring. |
| 6 | open | `README.md` (Source files table) | Lists `src/geojson_to_svg.py` and `src/generate_svg_data_js.py` — neither file exists. | Remove those rows (or add the files). |
| 7 | open | project root | No `requirements.txt`, so dependencies can't be installed in one step. | Create one with `pip freeze` (or list the key packages). |
| 8 | open | `src/test.py` | Only checks imports, and imports `anthropic`, which the app no longer uses. No automated tests exist. | Add unit tests for `parser.py` and `state_manager.py` (already listed as High in DEVLOG). |

## Not a bug (noted so I remember why)

- **Sector 3 is `None` in the live snapshot** (`src/server.py:205`) — the game only sends S1 and S2. S3 is calculated at lap end as `lap − S1 − S2` in `src/state_manager.py:180` and shows in lap history.
