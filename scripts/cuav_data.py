"""Local, label-safe access to the downloaded CUAVerifierBench split."""

from pathlib import Path

from datasets import Dataset, concatenate_datasets


DATASET_ID = "microsoft/CUAVerifierBench"
CONFIG = "trajectories"
SPLIT = "fara7b_om2w_browserbase"
CACHE_ROOT = Path("data/raw/cuaverifierbench/hf_cache")
ARROW_ROOT = (
    CACHE_ROOT
    / "microsoft___cua_verifier_bench"
    / CONFIG
    / "0.0.0"
    / "c19eb323cd802add5c3d2840ff13044061364867"
)


def load_frozen_split():
    """Load only the two local Arrow shards downloaded from the public split."""
    paths = sorted(ARROW_ROOT.glob("cua_verifier_bench-fara7b_om2w_browserbase-*.arrow"))
    if len(paths) != 2:
        raise FileNotFoundError(
            f"Expected two cached {SPLIT} Arrow shards under {ARROW_ROOT}; found {paths}"
        )
    return concatenate_datasets([Dataset.from_file(str(path)) for path in paths])
