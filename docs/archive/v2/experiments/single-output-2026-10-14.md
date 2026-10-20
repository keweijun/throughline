# Single output and host recording: three paired mechanism checks

Date: 2026-10-14 (user timezone). After user authorization, only isolated measurement scripts/materials were created. Production skill, UI, authentication, and real-course progress were unchanged.

## Conclusion

In this sample, streaming directly and recording the same text programmatically was faster than asking the model to write a full record before replying. All three pairs delivered the first 200 characters earlier and completed faster; Single lessons were slightly longer. This supports prioritizing the mechanism, without a native-desktop performance guarantee.

## Design and limits

- Both conditions requested gpt-6.1-sol / medium through the same configured custom Responses provider and local App Server stdio. Fresh ephemeral sessions, serial order S/D, D/S, S/D.
- Both received identical pages, background, and goals without preparation packages. Only recording differed: Double writes full answer-record.md before repeating it; Single lets the host save authoritative item/completed text with one model output.
- The 1600–2200-character target was a soft guide; tools were explicitly not to pad length. All actual outputs exceeded it. Record actual length and independently check required content rather than claiming identical scripts.
- Python monotonic timing measures stream-event arrival, chiefly the first 200 final-answer characters and full-turn completion. Preparation commentary is excluded. Internal first-token and actual UI rendering times were not measured.
- All final messages had final_answer phase; concatenated stream and authoritative items matched; host-record.md and final.md were byte-identical. Double's model record matched its reply; Single had no model-prewritten file.
- Teacher-stage configuration timestamps stayed constant, with no model/rerouted events. This does not authenticate routed backend model weights.
- This was not a native desktop conversation takeover. It changed no native persistence and did not test disconnect/crash/course transaction consistency.

## Measurements

| Section | Double first 200 | Single first 200 | Double complete | Single complete | Double/Single characters |
|---|---:|---:|---:|---:|---:|
| Photoelectric effect | 94.9 s | 34.1 s | 127.1 s | 69.6 s | 2417 / 2694 |
| Bohr model | 90.1 s | 31.5 s | 122.4 s | 83.8 s | 2375 / 2669 |
| Triangular wavefunction projection | 85.1 s | 28.9 s | 116.6 s | 76.7 s | 2498 / 2920 |

Mean first-200 time fell from 90.0 to 31.5 s. Aggregate full time fell from 366.1 to 230.1 s, a 37.1% observed reduction. Single visible text was about 13.6% longer overall; shorter explanations did not produce the result.

Reported output tokens totaled 11,851 versus 6,503, about 45.1% lower, including intermediate tool-related generation rather than just visible text. Original-image views were 5/5/2 for Single versus 3/3/2 for Double; Single did not gain by viewing fewer originals. Natural execution differences prevent precise attribution of every time difference.

## Independent content checks

All six scripts were renamed with R identifiers; reviewers did not read conditions, timing, or mappings. Original goals/pages supported passing all six without important physics errors, missing required derivations, or obvious paired-content reductions. Every first-200 segment was substantive teaching. One projection opening could distinguish wavefunction and probability-density plots more explicitly, a nonblocking wording improvement.

These checks measure correctness/coverage, not human understanding, fatigue, or outcomes. There was one run per condition/section, without significance testing or a stable-latency claim.

## Design implications

Unlike the mixed preparation experiment, this result was consistent and directly reduces repeated generation/model round trips. Prioritize adapting authoritative-reply capture rather than simply removing original-text recording requirements. Evidence and source retention remain constraints.

Next, establish how to capture authoritative final messages and associate courses in native chat, or do so in a custom client. This proves the experimental client can collect streams, identify final messages, and save them exactly; it does not establish native desktop integration.

## Raw materials

Ignored `work/output-benchmark` retains PROTOCOL.md, harness/run.py, installed-version protocol schemas, six event JSONLs, prompts, effective settings, lessons, records, metrics, analysis.json, and blinded quality checks. Original lectures and personal learning data were not uploaded.
