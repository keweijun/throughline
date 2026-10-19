# Branch selection browser check — 2026-10-19

Validated with headless Chromium and real mouse drags through the UI (`tests/branches_browser.cjs`), against the existing temporary navigation fixture and deterministic model boundary. This check makes no live-provider claim.

- Red: selecting a meaningful paragraph succeeded, but clicking `就这句提问` timed out because the contextual action did not exist.
- Green: a real paragraph drag selected `这是完整的讲解段落，保留阅读位`; contextual action opened the side panel with that exact excerpt.
- Submitted a question through the UI; returning to the mainline restored the saved reading scroll from **2719 to 2719 px**.
- Starting another question after submission retained no stale excerpt.
- A real mouse drag over a rendered KaTeX formula produced its original annotation `P=|a+b|^2`, avoiding duplicated visual/MathML text.
- Explicit clear removed the reference. The top entry no longer recaptures scroll: anchors are captured at selection time only.

The contextual action is positioned near the selection, bounded to the viewport, and hides when scrolling. A saved selection remains available through the ordinary entry. Keyboard selection capture is supported but not separately exercised in this check.

Run with `NODE_PATH` pointing to the installed Playwright package parent and `TEST_PYTHON` pointing to the project Python environment: `node tests/branches_browser.cjs`.
