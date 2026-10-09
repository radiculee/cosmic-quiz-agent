"""Runtime settings and model prices.

Every value has a safe default. Only the model can be overridden from the environment for now;
budgets and the domain allow-list are reviewed in code so changes show up in a diff.
"""

from __future__ import annotations

import os
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ModelPrice(BaseModel):
    """USD per million tokens for one model, used to log the cost of every run."""

    model_config = ConfigDict(frozen=True)

    input_per_mtok: float
    output_per_mtok: float
    cache_write_per_mtok: float
    cache_read_per_mtok: float

    def max_call_cost_usd(self, prompt_tokens: int, max_output_tokens: int) -> float:
        """The most one call can cost: every prompt token at the dearest input rate (a cache
        write) and the full output allowance."""
        input_rate = max(self.input_per_mtok, self.cache_write_per_mtok, self.cache_read_per_mtok)
        return (prompt_tokens * input_rate + max_output_tokens * self.output_per_mtok) / 1_000_000


# Anthropic first-party prices. Cache writes use the 5-minute TTL rate (1.25x input).
PRICES: dict[str, ModelPrice] = {
    "claude-haiku-4-5": ModelPrice(
        input_per_mtok=1.00,
        output_per_mtok=5.00,
        cache_write_per_mtok=1.25,
        cache_read_per_mtok=0.10,
    ),
}

DEFAULT_MODEL = "claude-haiku-4-5"

# The monthly spend limit set on the Anthropic Console workspace (CLAUDE.md hard rule 1).
# Anthropic enforces it; it is kept here only so the analytics page can show spend against it.
ANTHROPIC_MONTHLY_LIMIT_USD = 10.0

# Versions of the verdict definitions sent to Jev (the wording is in agent/verifiers/jev.py).
JevCriteria = Literal["generic-1", "astro-1"]

# Measured in Session 3: one Jev request per item costs about $0.0002 to $0.0003 on TypeSafe.
JEV_COST_PER_ITEM = 0.0003


def _default_path_prefixes() -> dict[str, tuple[str, ...]]:
    return {"arxiv.org": ("/abs/",)}


class Settings(BaseModel):
    """Configuration for one agent run."""

    model_config = ConfigDict(frozen=True)

    model: str = DEFAULT_MODEL
    max_output_tokens: int = Field(default=4096, gt=0)

    # Hard budgets enforced by the loop, whatever the model decides.
    max_steps: int = Field(default=12, gt=0)
    max_seconds: float = Field(default=120.0, gt=0)
    max_input_tokens: int = Field(default=200_000, gt=0)
    # Before every model call the loop checks that the spend so far plus an upper bound on that
    # call's cost stays within this. Set from a replay of the 180 bank-build runs under the
    # bound (2026-10-02): none would have been stopped at $0.10.
    max_run_cost_usd: float = Field(default=0.10, gt=0)

    # Tool behaviour.
    max_page_chars: int = Field(default=12_000, gt=0)  # about 3,000 tokens
    # Domains fetch_page may read (subdomains included), approved in Session 2.
    allowed_domains: tuple[str, ...] = (
        # Encyclopedia
        "wikipedia.org",
        # Space agencies and telescope institutes
        "nasa.gov",
        "esa.int",
        "esahubble.org",
        "esawebb.org",
        "stsci.edu",
        "webbtelescope.org",
        "hubblesite.org",
        # Research and observatories
        "arxiv.org",
        "eso.org",
        "noirlab.edu",
        "iau.org",
        # Popular science (lowest preference in the prompt)
        "space.com",
        "skyandtelescope.org",
        # britannica.com was removed in Session 2: it returns HTTP 403 to the agent.
    )
    # Domains where only some paths may be read: arXiv abstract pages, never PDFs or listings.
    allowed_path_prefixes: dict[str, tuple[str, ...]] = Field(
        default_factory=_default_path_prefixes
    )
    http_timeout_seconds: float = Field(default=15.0, gt=0)
    http_retries: int = Field(default=2, ge=0)
    http_retry_backoff_seconds: float = Field(default=1.0, ge=0)
    user_agent: str = "CosmicQuizAgent/0.1 (+https://github.com/radiculee/cosmic-quiz-agent)"

    # Verifiers (layers 2 and 3 of the publish gate).
    verifier_max_output_tokens: int = Field(default=2048, gt=0)
    # The Haiku verifier call is skipped (the item goes to review) if its cost bound exceeds this.
    # The highest bound in the bank build was $0.061.
    max_verifier_cost_usd: float = Field(default=0.07, gt=0)
    # Pinned so thresholds and the confidence players see stay stable across Jev releases.
    jev_model: str = "jev-1.13.0"
    # Chosen 2026-10-02 after a Jev-only re-check of the Session 3 eval (evals rejev): at the same
    # threshold, planted faults handled stayed 38/40 and Jev flagged two more of them itself;
    # generated items went from 22/20/9 to 23/19/9 published/review/discarded.
    jev_criteria: JevCriteria = "astro-1"
    jev_input_per_mtok: float = 0.042  # TypeSafe price; output tokens are free
    jev_threshold: float = Field(default=0.8, gt=0, lt=1)
    jev_timeout_seconds: float = Field(default=30.0, gt=0)

    runs_dir: str = "runs"

    @field_validator("model")
    @classmethod
    def _model_has_price(cls, value: str) -> str:
        if value not in PRICES:
            known = ", ".join(sorted(PRICES))
            raise ValueError(f"No price entry for model {value!r}; add it to PRICES ({known}).")
        return value

    @property
    def price(self) -> ModelPrice:
        return PRICES[self.model]

    @property
    def max_job_cost_usd(self) -> float:
        """The most one job (an agent run plus the Haiku verifier) can spend on Anthropic. Both
        limits are checked in code before every call, so this is a bound, not an estimate."""
        return self.max_run_cost_usd + self.max_verifier_cost_usd


def load_settings() -> Settings:
    """Load `.env` (if present) and build settings, applying supported overrides."""
    load_dotenv()
    model = os.environ.get("AGENT_MODEL", "").strip() or DEFAULT_MODEL
    return Settings(model=model)
