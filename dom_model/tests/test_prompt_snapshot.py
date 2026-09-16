from __future__ import annotations

import hashlib
from pathlib import Path

from dom_model import prompts


EXPECTED_PROMPT_SHA256 = {
    "ACTION_ONLY_RUBRIC_SCORER_PROMPT": "3d1748b76b09bfa27cc8750f73e5fb6c61ba9dddb2598c34b17bd0e1f1da9977",
    "CHECK_VALID_TASK_PROMPT": "8ea3cf7bb75648c22a60bcd90885f1725aa1d2cbafc1eee1d0c41120f17e76cc",
    "CHECK_VALID_TASK_WITH_TRAJECTORY_PROMPT": "f8162b333b3059cb2fb819dd3eb7fc86e0f0c95549e0d434a94e188f10df277a",
    "CONDITIONAL_CRITERIA_DISAMBIGUATION_PROMPT": "0c930aec9c06f7f1b21a5a65578313c0bb36d282e07d7794c89999945e62073f",
    "FIRST_POINT_OF_FAILURE_PROMPT": "444f1805b5e7f31f8913387cc952edd69a27b7902be0c159dd76667d0c975350",
    "MM_CRITERION_RESCORING_PROMPT": "b422fc3992213d44a08dceff2be878596c2e148a65ef36d755f7a1f06439b747",
    "MM_RUBRIC_RESCORING_PROMPT": "de5c6190e0819069827f4cddb7b6cc0bb4d917587dfea50572ef94246a232b27",
    "OUTCOME_VERIFICATION_PROMPT": "2ecdca4b098343f417fb08989b7c545a4b58e31ddf7b23774d080bb1a1138091",
    "PENALIZE_UNSOLICITED_SIDE_EFFECTS_PROMPT": "99965517e7f99c2c221035eaf7d6e8269258bd613a8362470794d389f58db23d",
    "RUBRIC_DEPENDENCY_CHECKING_PROMPT": "dbe7735b7351784e997d31348287d5dc67fbdf6be57b9e0387491f0964a5c43a",
    "RUBRIC_GENERATION_PROMPT_TEMPLATE": "e18576217d1e4ba1fda4f56ec85d6322c7c7fa69efe8b787e4a70aef451eefae",
    "RUBRIC_REALITY_CHECK_PROMPT": "84067b3b4e85031199e7e56b739ad8bfe4c63db628b9d364f339d879d746e08d",
}


def test_active_prompt_text_is_byte_for_byte_stable():
    actual = {
        name: hashlib.sha256(getattr(prompts, name).encode("utf-8")).hexdigest()
        for name in EXPECTED_PROMPT_SHA256
    }
    assert actual == EXPECTED_PROMPT_SHA256


def test_prompt_source_is_directly_dom_native():
    source = Path(prompts.__file__).read_text(encoding="utf-8")
    assert "_use_dom_model_terminology" not in source
    assert "screenshot" not in source.lower()
