from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Every field can be set from the environment or backend/.env as RIVER_<NAME>.

    Complex values are JSON, e.g. RIVER_RETURN_RANGES='{"near": [30, 90], "any": [30, 1095], "far": [730, 1825]}'.
    """

    model_config = SettingsConfigDict(env_prefix="RIVER_", env_file=BACKEND / ".env", extra="ignore")

    database_url: str = "postgresql+psycopg://river:river@localhost:54329/river"
    # Enables fake auth (X-Dev-User), the dev clock and other /api/dev routes. Never on in production.
    dev_mode: bool = False

    # Supabase Auth. Tokens signed with the project's asymmetric keys are checked against
    # {supabase_url}/auth/v1/.well-known/jwks.json; legacy HS256 tokens need the JWT secret.
    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    supabase_jwt_audience: str = "authenticated"

    default_tz: str = "Asia/Kolkata"
    free_catches_per_day: int = 5
    writes_per_day: int = 3

    message_min: int = 20
    message_max: int = 500
    note_min: int = 2
    note_max: int = 140

    # Hidden return windows, in days after writing. Never sent to the client.
    # No message returns before cooling_days, whatever the ranges say.
    cooling_days: int = 30
    return_ranges: dict[str, tuple[int, int]] = {
        "near": (30, 90),
        "any": (30, 1095),
        "far": (730, 1825),
    }

    report_hide_threshold: int = 3

    @model_validator(mode="after")
    def _check_ranges(self) -> Self:
        unknown = set(self.return_ranges) - {"near", "any", "far"}
        if unknown:
            raise ValueError(f"Unknown return options: {sorted(unknown)}")
        for name, (lo, hi) in self.return_ranges.items():
            if not 0 <= lo <= hi:
                raise ValueError(f"Return range {name!r} must satisfy 0 <= lo <= hi, got ({lo}, {hi})")
        return self

    @property
    def supabase_issuer(self) -> str:
        return self.supabase_url.rstrip("/") + "/auth/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
