# Standalone Refined DOM-Diff Text Verifier

This package contains the complete normal, uncapped refined DOM-text verifier:
strict dom_diffN.txt parsing, deterministic compaction, relevance, top-K,
criterion retrieval, packed analysis, validation, downstream scoring, clients,
metrics, and runner.

It imports neither the old repository nor another benchmark verifier. Every
run requires one canonical frozen rubric through the rubric-file CLI option;
the canonical SHA-256 is checked before judge clients are initialized.
