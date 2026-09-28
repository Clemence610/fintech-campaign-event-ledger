from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, HTTPException

from .infrai_email import InfraiEmail, InfraiError
from .risk_policy import CampaignDecision, PaymentEvent, PaymentState, decide_action

service = FastAPI(title="Payment campaign event ledger")
records: dict[str, dict[str, Any]] = {}


def email_client() -> InfraiEmail:
    return InfraiEmail()


def client_error(exc: InfraiError) -> HTTPException:
    status = exc.status_code if 400 <= exc.status_code < 500 else 502
    return HTTPException(status_code=status, detail={"code": exc.code, "error": exc.detail})


@service.post("/payments/notify", response_model=CampaignDecision, status_code=201)
def notify_payment(
    payment: PaymentEvent, client: InfraiEmail = Depends(email_client)
) -> CampaignDecision:
    existing = records.get(payment.payment_id)
    if existing:
        return CampaignDecision(**existing["decision"])
    try:
        message_id, metadata = client.send_audit_notice(
            to=payment.recipient,
            payment_id=payment.payment_id,
            amount_minor=payment.amount_minor,
            currency=payment.currency.upper(),
        )
    except InfraiError as exc:
        raise client_error(exc) from exc

    decision = CampaignDecision(
        payment_id=payment.payment_id,
        message_id=message_id,
        state=PaymentState.HOLD,
        reason="audit notice sent; awaiting engagement",
        audit=["payment_recorded", "audit_notice_sent", "risk_action_held"],
    )
    records[payment.payment_id] = {
        "payment": payment.model_dump(),
        "metadata": metadata,
        "decision": decision.model_dump(),
    }
    return decision


@service.post("/payments/{payment_id}/reconcile", response_model=CampaignDecision)
def reconcile_payment(
    payment_id: str, client: InfraiEmail = Depends(email_client)
) -> CampaignDecision:
    record = records.get(payment_id)
    if not record:
        raise HTTPException(status_code=404, detail="payment not found")
    current = CampaignDecision(**record["decision"])
    try:
        events = client.list_events(current.message_id)
    except InfraiError as exc:
        raise client_error(exc) from exc

    payment = PaymentEvent(**record["payment"])
    state, reason = decide_action(payment, events)
    updated = current.model_copy(
        update={
            "state": state,
            "reason": reason,
            "audit": current.audit + [f"events_reconciled:{state.value}"],
        }
    )
    record["decision"] = updated.model_dump()
    return updated
