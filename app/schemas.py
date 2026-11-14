from datetime import date
from pydantic import BaseModel, Field, field_validator


def normalize_mac(value: str) -> str:
    compact = value.replace("-", ":").upper()
    parts = compact.split(":")
    if len(parts) != 6 or any(len(part) != 2 for part in parts):
        raise ValueError("Invalid MAC address")
    try:
        int("".join(parts), 16)
    except ValueError as error:
        raise ValueError("Invalid MAC address") from error
    return ":".join(parts)


class TenantInput(BaseModel):
    room_number: str = Field(min_length=1)
    ssid: str = Field(min_length=1)
    due_day: int = Field(ge=1, le=31)
    last_payment_date: date
    mac_addresses: list[str] = Field(min_length=1)

    @field_validator("mac_addresses")
    @classmethod
    def validate_macs(cls, values: list[str]) -> list[str]:
        normalized = [normalize_mac(value) for value in values]
        if len(set(normalized)) != len(normalized):
            raise ValueError("Duplicate MAC addresses")
        return normalized


class PaymentInput(BaseModel):
    payment_date: date | None = None
