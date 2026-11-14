import re
from datetime import date
from pydantic import BaseModel, Field, field_validator


def normalize_mac(value: str) -> str:
    hex_only = re.sub(r"[^0-9A-Fa-f]", "", value)
    if len(hex_only) != 12:
        raise ValueError(
            f"Invalid MAC address '{value}': must contain exactly 12 hex characters."
        )
    return ":".join(
        hex_only.upper()[index:index + 2] for index in range(0, 12, 2)
    )


class TenantInput(BaseModel):
    room_number: str = Field(min_length=1)
    ssid: str = Field(min_length=1)
    due_day: int = Field(ge=1, le=31)
    last_payment_date: date
    mac_addresses: list[str] = Field(default_factory=list)

    @field_validator("mac_addresses")
    @classmethod
    def validate_macs(cls, values: list[str]) -> list[str]:
        normalized = [normalize_mac(value.strip()) for value in values if value.strip()]
        if len(set(normalized)) != len(normalized):
            raise ValueError("Duplicate MAC addresses")
        return normalized


class PaymentInput(BaseModel):
    payment_date: date | None = None
