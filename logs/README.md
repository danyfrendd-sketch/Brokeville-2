# Brokeville 2 — error logs

This folder is for diagnostic reports and notes.

## Important: GitHub Pages cannot write into this folder

The published game is static website content. A browser cannot create or append files in the GitHub repository. The game therefore records client-side errors in browser memory and (when allowed) localStorage, then lets the player download a JSON report.

## How to collect a report

1. Open https://danyfrendd-sketch.github.io/Brokeville-2/play.html
2. If loading freezes, wait for the timeout/error message.
3. Tap **СКАЧАТЬ ЛОГИ** to download a file named `brokeville2-error-log-….json`.
4. Send that JSON file in the project chat. Do not paste secrets or private information into logs.

The logger records timestamps, error/rejection messages, stack traces when available, page URL, browser user-agent, and loading-progress anomalies. It clamps the visible progress indicator to 100%; a value above 100% was a progress-reporting anomaly, not a meaningful loading percentage.

A hard browser/process crash may prevent JavaScript from writing the final log entry. If the browser fully freezes, the timeout handler runs only after it becomes responsive again.
