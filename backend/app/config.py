from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RIVER_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://river:river@localhost:54329/river"
    dev_mode: bool = True  # enables fake auth (X-Dev-User) and /dev routes

    default_tz: str = "Asia/Kolkata"
    free_catches_per_day: int = 5
    writes_per_day: int = 3

    message_min: int = 20
    message_max: int = 500
    note_min: int = 2
    note_max: int = 140

    # Hidden return windows, in days after writing. Never sent to the client.
    cooling_days: int = 30
    return_ranges: dict[str, tuple[int, int]] = {
        "near": (30, 90),
        "any": (30, 1095),
        "far": (730, 1825),
    }

    report_hide_threshold: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
