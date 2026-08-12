"""Standalone verifier for Stagehand semantic browser trajectories."""

from .schemas import VerifierConfig
from .agent import StagehandVerifier

__all__ = ["StagehandVerifier", "VerifierConfig"]
__version__ = "0.1.0"

