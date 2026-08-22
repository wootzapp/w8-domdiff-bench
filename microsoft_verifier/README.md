# Standalone Microsoft Screenshot Verifier

This package is a self-contained copy of the Microsoft screenshot-based
Universal Verifier runtime. It does not import the old repository or any
other benchmark verifier.

Every run requires one canonical rubric through the rubric-file CLI option.
The rubric is loaded before clients are created, validated against the task,
and its canonical SHA-256 is included in the result receipt.
