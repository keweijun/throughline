# Branch selection browser check — 2026-10-19

Validated with headless Chromium and real mouse drags through the UI (`tests/branches_browser.cjs`), against the temporary navigation fixture and deterministic model boundary. This makes no live-provider claim. The original run used Chinese fixture text; the actions and excerpt are translated below, with its original scroll measurements retained.

- Red: selecting a meaningful paragraph worked, but clicking "Ask about this passage" timed out because the contextual action did not exist.
- Green: a real paragraph drag selected an excerpt meaning "This is a complete lesson paragraph, preserving the reading position"; the contextual action opened the panel with the exact selected text.
- Submitted a question in the UI; return restored reading scroll from **2719 to 2719 px**.
- Starting another question retained no stale excerpt.
- Dragging over rendered KaTeX produced original TeX `P=|a+b|^2` without duplicated visual/MathML text.
- Explicit clear removed the reference. The top entry no longer recaptures scroll; anchors are captured at selection time.

The contextual action is positioned near selection, bounded to the viewport, and hidden on scroll. Saved selection remains through the ordinary entry. Keyboard capture is supported but was not separately exercised.

Run with NODE_PATH pointing to the installed Playwright package parent and TEST_PYTHON to the project Python: `node tests/branches_browser.cjs`.
