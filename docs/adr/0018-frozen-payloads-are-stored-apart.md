# Frozen prompt snapshots and prepared material are stored apart from the records that list them

A course stores every record as one JSON document (ADR 0001). Each turn froze the prompt data it was taught from (`prompt_snapshot`: the section's context and sources, the route, the session, course memory), and a resumed turn kept a copy for every earlier attempt. A preparation job kept its snapshot and the material it prepared. Those payloads are nearly all of the data: in a course with 70 sections and 250 turns, prompt snapshots were 21 of the 22 MB of turns, and snapshots and material were 2.7 MB of the 2.75 MB of preparation jobs.

The payloads are read rarely: when a prompt is built, by completion hooks, and by preparation prompts. The records around them are read constantly: the interface lists every turn after each action, the host stores streamed text a few times a second, and background scheduling lists every preparation job every few seconds. Listing, decoding and rewriting the payloads with them made opening a large course take over a second and every action lag.

Each payload now lives in its own record under the same key:

- `stream_snapshots/<turn id>` holds the turn's `prompt_snapshot` and each earlier attempt's, as `attempts`. The turn keeps everything else, plus `title`, its section's title as the snapshot froze it, which listings show.
- `preparation_payloads/<job id>` holds the job's `snapshot` and `content`. The job keeps the snapshot's `fingerprint` and `language`, which reconciling and scheduling compare.

`streaming.save` and `preparation.save` split a record when they store it, and `streaming.load` and `preparation.load` join it again. A record read without its payload is stored without touching the payload, so streamed text and status changes never rewrite a snapshot. Operations return what they returned before: `stream.read`, `stream.start`, `stream.resume` and `stream.list` give whole turns, and `preparation.view` and `preparation.enqueue` give whole jobs. The frequent writes (`stream.event`, `stream.events`, `stream.pause`, `stream.recover`) return the turn without its snapshots; the host reads the whole turn once a turn completes, for the completion hooks.

Migration 7 (ADR 0007) moves the payloads of existing courses. A course written before it cannot be read by an older Throughline afterwards, which ADR 0007 already prevents.

The cost is a second read whenever a whole turn or job is needed, and code that stores turns or jobs must go through `save`, never `store.put`, or a payload ends up back in the listed record.
