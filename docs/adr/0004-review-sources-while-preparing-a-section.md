# Review sources while preparing a section

Source units start `pending` verification: extraction can garble formulas and figures, so a unit is only `verified` after someone compares it with the original. Reviewing every unit when a course is created is the most expensive point to do it. Learners skip and reorder sections, and re-registering a changed file resets its units anyway. So course creation only flags failed and empty pages, and the substantive review happens just in time, while the host prepares a section.

Each preparation job lists the section's linked units that are still pending, current and successfully extracted (at most eight). The host attaches each PDF page as an image rendered from the exact revision; a Markdown line is its own original. The teacher appends a `<source-review>` block, and when the job becomes ready the host records it with `curriculum.verify`. When no position exists yet, the host prepares the first route section, so the first lesson gets the same review.

The host records only the job's own targets, and a PDF page can be verified only if its image was attached. Source text cannot verify other units, and a page without a renderer stays pending. Coverage and verification are excluded from preparation fingerprints, so recording a review does not discard prepared material.

The runner interface becomes `run(prompt, cwd, emit, cancel, images=())`. The host passes `images` only when a turn has attachments, so runners that never receive them can keep the four-argument form.
