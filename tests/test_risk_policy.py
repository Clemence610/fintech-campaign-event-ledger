from campaign_service.risk_policy import PaymentEvent, PaymentState, decide_action


def payment(risk_score: int = 35) -> PaymentEvent:
    return PaymentEvent(
        payment_id="pay-42",
        recipient="reviewer@example.com",
        amount_minor=8400,
        currency="USD",
        risk_score=risk_score,
    )


def test_bounce_routes_payment_to_manual_review() -> None:
    state, reason = decide_action(payment(), [{"type": "bounce"}])
    assert state is PaymentState.MANUAL_REVIEW
    assert reason == "campaign notice bounced"


def test_open_releases_lower_risk_payment() -> None:
    state, reason = decide_action(payment(), [{"type": "open"}])
    assert state is PaymentState.RELEASE
    assert reason == "campaign notice opened"


def test_open_keeps_elevated_risk_in_review() -> None:
    state, _ = decide_action(payment(risk_score=91), [{"type": "open"}])
    assert state is PaymentState.MANUAL_REVIEW
