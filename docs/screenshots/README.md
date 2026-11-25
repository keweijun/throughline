# README screenshots

The screenshots in the READMEs (`docs/images/{library,lesson,reader,questions,studio,review}-{en,zh-CN}.png`) are taken in a throwaway library built from the files here, so they can be taken again after the interface changes.

The screenshot course, *Quantum Mechanics I* (量子力学（上） in Chinese), is made up: lecture notes and a problem set written for it (`src/`), taught by the real Codex teacher to a learner who studied the first chapter and the first section of the second, got one exercise wrong and asked one question on the side. `courses/` keeps it in both languages as course packages, taught already, so retaking the screenshots needs no model time. The six other courses on the library page only have a cover and a route.

## Retaking the screenshots

From the repository root, with `.venv` and `web/node_modules` installed:

```sh
for lang in en zh-CN; do
  .venv/bin/python docs/screenshots/build.py $lang work/shots/$lang --package docs/screenshots/courses/quantum-$lang.throughline
done
.venv/bin/python docs/screenshots/host.py work/shots/en 8793 &
.venv/bin/python docs/screenshots/host.py work/shots/zh-CN 8794 &
(cd docs/screenshots && node shots.mjs 8793 en ../images && node shots.mjs 8794 zh-CN ../images)
kill %1 %2
```

`shots.mjs` opens the course, takes the library, Learn at *Adding amplitudes*, the cited page in the reader, the side question, Studio and Review, at 1440×900 and twice the pixel density, and asks Studio for the formula sheet again, since `studio.py` keeps chats only while it runs. Look at every image before committing it: a change to the interface can move what a step clicks.

## Pieces

- `build.py` makes the library in `<out>/library` and per-user settings in `<out>/config`, with the first-run series and one-time tips taken as seen.
- `host.py` serves it with the real Codex teacher (lessons, answers, drills) and `studio.py` as Studio's Codex: a stand-in that replays `studio-scripts.json`, so the Studio screenshot shows the same chat every time. `sheet.py` saves the formula sheet that chat says it wrote; the packages hold it already.
- `drive.mjs` is how the course was taught: it clicks through lessons, answers checks and exercises, asks a side question, starts a drill and sends a Studio message, one command at a time (see its header). It prints what the page shows, formulas as TeX, so you can answer.

## Teaching the course again

When lessons, practice or Review change enough that the saved courses look old, build without `--package` (the course is then untaught, and `build.py` prints the PDFs from `src/` with `pdf.mjs`), serve it, and study it with `drive.mjs` as before: the three sections of *The wavefunction* with their exercises, one wrong answer that stays wrong in a drill so Mistakes has an entry, then *Adding amplitudes* in full, the question about "The mixed products are complex conjugates…" (为什么虚部会抵消…), and the Studio message from `studio-scripts.json`. Then save the course over its package:

```sh
THROUGHLINE_HOME=work/shots/en/library .venv/bin/python -m throughline export quantum --level everything --out docs/screenshots/courses/quantum-en.throughline
THROUGHLINE_HOME=work/shots/zh-CN/library .venv/bin/python -m throughline export liangzi --level everything --out docs/screenshots/courses/quantum-zh-CN.throughline
```

A course package from an older Throughline opens in a newer one, so the packages only need replacing when the screenshots should show something new.
