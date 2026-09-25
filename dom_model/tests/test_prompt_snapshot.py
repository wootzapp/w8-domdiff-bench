from __future__ import annotations

import hashlib
import re
from pathlib import Path

from dom_model import prompts


EXPECTED_PROMPT_SHA256 = {
    "ACTION_ONLY_RUBRIC_SCORER_PROMPT": "f5d939a4d0f637c9d6e0e5d20fd684eaf648e423a0810a0d5761fdb874a6c1b5",
    "CHECK_VALID_TASK_PROMPT": "8ea3cf7bb75648c22a60bcd90885f1725aa1d2cbafc1eee1d0c41120f17e76cc",
    "CHECK_VALID_TASK_WITH_TRAJECTORY_PROMPT": "50e4cc82f26e5ac69b5592a3ec1289f84b1139615d3c90a298c726deb5375e04",
    "CONDITIONAL_CRITERIA_DISAMBIGUATION_PROMPT": "0c930aec9c06f7f1b21a5a65578313c0bb36d282e07d7794c89999945e62073f",
    "FIRST_POINT_OF_FAILURE_PROMPT": "0ea759c5c0bd4e7ffa03ddc7facfe632db81eb70b0d9519db1b70176f02f36c7",
    "MM_CRITERION_RESCORING_PROMPT": "5d115d4198d6d28daee59ad80ec6556ae081c6f752be225011b0e474344a9040",
    "MM_RUBRIC_RESCORING_PROMPT": "4d95836856d646c40eb082125fb0d7c2ba7f289297d5e9f97234d7de3964f848",
    "OUTCOME_VERIFICATION_PROMPT": "0d02d5c650e867561a593f9e5c2c450263747b18dca21bb7261f3c7155f13d2f",
    "PENALIZE_UNSOLICITED_SIDE_EFFECTS_PROMPT": "cf698f41460673055f6444c1ca1f5292b735fb93b4d1c3195d71ff1e3ee19cfe",
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
    assert "DOM-model" in source
    legacy_terms = ("screen" + "shot", "im" + "age", "vis" + "ual")
    assert all(not re.search(rf"\b{term}\w*\b", source, re.I) for term in legacy_terms)
