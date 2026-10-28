# Seed-state analyses

These secondary analyses use the same ten validation images, four growth rules, five corruption families, original severities and realizations. They do not change the held-out decision rule or select new primary settings.

## Reproduce the tables without segmentation

From the checkout, use new output directories:

```text
python experiments/analyze_matched.py --matched-dir evidence/seed_state/matched --baseline-records experiments/runs/bsds500_multicorruption_v2_validation_10x160_r2.jsonl --baseline-inference reports/generated/validation_10x160_r2_attribution_20260918/inference.csv --output-dir results/matched_analysis_new
python experiments/analyze_sensitivity.py --sensitivity-dir evidence/seed_state/sensitivity --baseline-records experiments/runs/bsds500_multicorruption_v2_validation_10x160_r2.jsonl --baseline-inference reports/generated/validation_10x160_r2_attribution_20260918/inference.csv --output-dir results/sensitivity_analysis_new
```

The supplied matched results have 1,680 paired records (560 original conditions, three fixed draws) and 560 seed diagnostics. Matching preserves maxima/minima counts separately and each source's initial intensity statistics; both branches use a common clean reference from the selected clean subset. Draws, replicates and severities are averaged before image-level inference. The change in original versus matched magnitude is not a mediation fraction because the clean reference changes.

The new sensitivity records cover ten neighboring variants: eight sigma settings and two CLERG tolerance settings. The four original baselines are reused, not rerun. All 2,900 records are retained: 2,810 ok, six no_seeds and 84 no_clean_reference. There are 1,400 prescribed pairs, of which 45 are undefined. Of 50 new variant-family groups, 35 have all ten defined image effects; 15 are NA (12 with 9/10 and three blur groups with 8/10). Missing conditions propagate rather than being omitted or scored zero. Full parameter-axis tables include 75 rows because the CLERG baseline is shown on both parameter axes; these are configurations, not independent images.

The original 240 clean-only screening records and their summary are included. They document the adopted policies on development images; no per-corruption fitting or parameter reselection is introduced. The complete held-out primary table is copied directly from the original inference CSV.

## New segmentation runs

After fetching the dataset into this checkout, use one of these new output directories:

```text
python experiments/run_revision_supplement.py --source-root . --kind matched --output-dir results/matched_new
python experiments/run_revision_supplement.py --source-root . --kind sensitivity --output-dir results/sensitivity_new
```

The input project can instead be an explicit separate project containing the matching validation configuration, manifest and data. Output paths must remain under this checkout's results/. A pilot uses the first image and first corruption condition and is only an execution check. Immutable source/configuration checks prevent cross-version resume.

## Archive and source provenance

Runtime records are copied byte-for-byte. Machine-specific source/revision root coordinates in the two supplementary metadata files are replaced by symbolic coordinates in new portable copies. Their scientific protocols, dataset hashes, dependency versions and recorded source hashes remain unchanged. ARCHIVE_DERIVATION.json records both original and portable metadata/done hashes; the original runtime files remain in the experiment archive. The accompanying done copies link to the portable metadata and explicitly identify their derivation. A grid-complete PASS does not mean every prediction is defined.

Each source_snapshots/<analysis>/ tree exactly matches the source hashes recorded for that run, including the earlier matched run. These are audit snapshots; execute new runs through experiments/run_revision_supplement.py in this checkout. The current supplementary runner adds empty-state handling and portable input-root selection without changing the numerical growth kernels or valid-case metric definitions. The current source and the recorded source snapshots have separate hashes. Old primary/strict/held-out provenance remains documented in ARCHIVED_RUN_PROVENANCE.md.
