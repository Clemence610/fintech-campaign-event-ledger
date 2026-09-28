from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class PaymentState(StrEnum):
    HOLD = "hold"
    RELEASE = "release"
    MANUAL_REVIEW = "manual_review"


class PaymentEvent(BaseModel):
    payment_id: str = Field(min_length=1)
    recipient: str
    amount_minor: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    risk_score: int = Field(ge=0, le=100)


class CampaignDecision(BaseModel):
    payment_id: str
    message_id: str
    state: PaymentState
    reason: str
    audit: list[str]


def event_kind(event: dict[str, Any]) -> str:
    value = event.get("type", event.get("event", ""))
    return str(value).lower()


def decide_action(payment: PaymentEvent, events: list[dict[str, Any]]) -> tuple[PaymentState, str]:
    kinds = {event_kind(event) for event in events}
    if "bounce" in kinds or "bounced" in kinds:
        return PaymentState.MANUAL_REVIEW, "campaign notice bounced"
    if "open" in kinds or "opened" in kinds:
        if payment.risk_score >= 80:
            return PaymentState.MANUAL_REVIEW, "opened notice with elevated payment risk"
        return PaymentState.RELEASE, "campaign notice opened"
    return PaymentState.HOLD, "awaiting a campaign open event"
