from functools import lru_cache
from pydantic import BaseModel, ConfigDict, Field, model_validator

from pydantic_settings import BaseSettings, SettingsConfigDict


class MudLossPolicy(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    version: str = "mud-loss-gates/2.0"
    lesson_distance_m: float = Field(default=300, ge=0)
    approach_distance_m: float = Field(default=100, ge=0)
    flow_deficit_min_l_min: float = Field(default=30, ge=0)
    flow_deficit_fraction: float = Field(default=.05, ge=0, le=1)
    flow_sustained_min_samples: int = Field(default=3, ge=2)
    flow_sustained_min_s: float = Field(default=20, gt=0)
    pit_drop_min_m3: float = Field(default=.5, gt=0)
    trend_min_s: float = Field(default=30, gt=0)
    trend_max_s: float = Field(default=120, gt=0)
    acquisition_gap_max_s: float = Field(default=30, gt=0)
    sample_skew_max_s: float = Field(default=10, ge=0)
    ecd_max_difference_sg: float = Field(default=.15, gt=0)
    ecd_similar_difference_sg: float = Field(default=.03, ge=0)
    ecd_weight_scale_sg: float = Field(default=.2, gt=0)
    ecd_weight_floor: float = Field(default=.4, ge=0, le=1)
    mud_weight_tolerance_sg: float = Field(default=.15, gt=0)
    hole_section_tolerance_in: float = Field(default=.5, ge=0)
    basis: str = "Uncalibrated synthetic demonstration thresholds; not an operational alarm"

    @model_validator(mode="after")
    def ordered(self):
        if self.lesson_distance_m < self.approach_distance_m or self.trend_max_s < max(self.trend_min_s, self.flow_sustained_min_s):
            raise ValueError("Look-ahead and trend windows must be ordered")
        return self


class HistoricalPolicy(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    version: str = "analog-evidence/2.1"
    minimum_weight: float = Field(default=.08, ge=0, le=1)
    alpha: float = Field(default=1, gt=0)
    beta: float = Field(default=1, gt=0)
    elevated_min_support: int = Field(default=2, ge=1)
    elevated_min_n_eff: float = Field(default=3, ge=1)
    elevated_min_p_hat: float = Field(default=.45, ge=0, le=1)
    threshold_basis: str = "Uncalibrated prototype policy; requires backtesting and expert validation"


class Settings(BaseSettings):
    demo_mode: bool = False
    serve_frontend: bool = False
    app_name: str = "eRTMAC-NWIS API"
    environment: str = "development"
    database_url: str = "sqlite+pysqlite:///./nwis.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    channel_freshness_s: dict[str, float] = Field(default_factory=dict)
    mud_loss_policy: MudLossPolicy = Field(default_factory=MudLossPolicy)
    historical_policy: HistoricalPolicy = Field(default_factory=HistoricalPolicy)

    @model_validator(mode="after")
    def freshness(self):
        import math
        if any(not math.isfinite(v) or v <= 0 for v in self.channel_freshness_s.values()):
            raise ValueError("Freshness thresholds must be finite and positive")
        return self

    model_config = SettingsConfigDict(
        env_prefix="NWIS_", env_file=".env", extra="ignore"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
