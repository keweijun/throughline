# Open the learning app

Run `guided-learning open <course-name>`. It starts the local interface in the background, or reuses the one already running, switches it to that course, opens a browser and prints the address. Give the learner that address and say which course is open and whether source verification is still pending. `guided-learning open` without a name opens the course library.

The host keeps running after the command returns and starts Codex for each lesson, so run `open` with escalated permissions outside the sandbox. `guided-learning stop` ends it. If it does not start, report the end of the log file named in the error.

A course needs a nonempty route (`curriculum.view`) before lessons can start; prepare it first if it is missing. Never substitute another course merely because it exists locally.

The app listens on loopback only. If Codex runs on a different machine from the learner's browser, the address is not reachable from their computer; explain that rather than claiming the page is open, and never expose the host on a public interface.

The Codex CLI supplies the teacher model. If a lesson fails, keep the course and any partial response, report the actual error, and help the learner check their Codex setup. A page load does not prove a lesson can complete.
