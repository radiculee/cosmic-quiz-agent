"""Runtime settings and model prices.

Every value has a safe default. Only the model can be overridden from the environment for now;
budgets and the domain allow-list are reviewed in code so changes show up in a diff.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ModelPrice(BaseModel):
    """USD per million tokens for one model, used to log the cost of every run."""

    model_config = ConfigDict(frozen=True)

    input_per_mtok: float
    output_per_mtok: float
    cache_write_per_mtok: float
    cache_read_per_mtok: float


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


class Settings(BaseModel):
    """Configuration for one agent run."""

    model_config = ConfigDict(frozen=True)

    model: str = DEFAULT_MODEL
    max_output_tokens: int = Field(default=4096, gt=0)

    # Hard budgets enforced by the loop, whatever the model decides.
    max_steps: int = Field(default=12, gt=0)
    max_seconds: float = Field(default=120.0, gt=0)
    max_input_tokens: int = Field(default=200_000, gt=0)

    # Tool behaviour.
    max_page_chars: int = Field(default=12_000, gt=0)  # about 3,000 tokens
    allowed_domains: tuple[str, ...] = ("wikipedia.org", "nasa.gov", "esa.int")
    http_timeout_seconds: float = Field(default=15.0, gt=0)
    user_agent: str = "CosmicQuizAgent/0.1 (+https://github.com/radiculee/cosmic-quiz-agent)"

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


def load_settings() -> Settings:
    """Load `.env` (if present) and build settings, applying supported overrides."""
    load_dotenv()
    model = os.environ.get("AGENT_MODEL", "").strip() or DEFAULT_MODEL
    return Settings(model=model)
