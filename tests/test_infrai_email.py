import httpx

from campaign_service.infrai_email import InfraiEmail


def test_send_boundary_uses_idempotency_and_default_sender() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["headers"] = dict(request.headers)
        captured["body"] = request.content.decode()
        return httpx.Response(200, json={"ok": True, "data": {"message_id": "msg-7"}})

    client = InfraiEmail(api_key="test-key", transport=httpx.MockTransport(handler))
    message_id, _ = client.send_audit_notice(
        to="reviewer@example.com",
        payment_id="pay-42",
        amount_minor=8400,
        currency="USD",
    )
    assert message_id == "msg-7"
    assert captured["method"] == "POST"
    assert "payment-notice-pay-42" in str(captured["headers"])
    assert '"from"' not in str(captured["body"])
