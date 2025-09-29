Jellystat - Project TODO

This document summarizes what was implemented during the session, what's pending, and suggested next features.

Completed work
- Restored project files from tag `v0.1.0` and committed the restore.
- Implemented CPU & RAM monitoring: per-core percentages, overall CPU percent, CPU frequency where available, and memory stats.
- Implemented network monitoring with per-interface counters, per-second rates (computed from diffs) and settings to choose interface and baseline.
- Moved server config injection to JSON script tag to avoid Jinja-in-JS issues and provided safe default config values.
- UI/UX polish: left sidebar (Dashboard & Settings), themes, preloader, deferred autoscale, and style updates.
- Implemented resilient client polling with exponential backoff and a visible fetch-error banner.
- Added small source-map endpoints and inline favicon to reduce DevTools noise.
- Created backups zip and initialized git repo, added `.gitignore`, CI workflow (flake8), and pushed initial commits and tag `v0.1.0`.
- Added screenshots to `README.md` and stored images under `docs/images/`.
- Created a recovery branch on GitHub (so the restored files are preserved remotely).

Pending / Not started
- Graphs for historical metrics (time-series graphs for CPU, RAM, network).
- Persistent timeseries storage (SQLite or similar) to store historical samples for graphing.
- Real-time updates (WebSocket or Server-Sent Events) to reduce polling and provide lower-latency updates.
- Authentication & access control for the UI and API endpoints.
- Dockerfile and docker-compose for containerized deployment.
- More comprehensive tests and CI (run unit tests, endpoint tests, etc.).
- Packaging for distribution (pip package or Windows installer).
- Platform service support (systemd unit file, Windows service wrapper).
- Mobile/responsive UI and accessibility improvements.
- Create a GitHub Release and attach artifacts.

Suggested next features (low-effort -> high-effort)
1. Add graphs (low-to-medium):
   - Use a lightweight charting library (Chart.js, Plotly, or lightweight alternatives) on the front-end.
   - Gather samples on the client and/or server and render CPU/RAM/Network time series.
   - UI: Add a small timeline under each gauge to show recent activity.
2. Persist samples (medium):
   - Store periodic samples (1s or 5s) in SQLite (rolling window) with a simple cleanup policy (keep 24h by default).
   - Provide endpoints to query historical ranges for charts.
3. Real-time updates (medium):
   - Implement SSE (Server-Sent Events) which is relatively simple with Flask and works well for one-way streaming.
   - Alternatively add optional WebSocket support.
4. Authentication (medium):
   - Add a config option for basic auth (username/password in `config.json`) or integrate with reverse-proxy.
5. Docker + docs (low):
   - Provide `Dockerfile` and `docker-compose.yml` for quick local deployment.
6. Tests & CI (medium):
   - Add pytest-based unit tests for the API endpoints and simple integration tests.

If you'd like, I can open issues or create smaller PR-sized tasks for each pending item. I can also implement 1 or 2 of the suggested features next (graphs + SQLite backend are a natural next step).
