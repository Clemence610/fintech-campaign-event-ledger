import os

from fastapi.testclient import TestClient

from campaign_service.payment_campaign import service


def main() -> None:
    recipient = os.environ.get("CAMPAIGN_EMAIL_TO")
    if not recipient:
        raise RuntimeError("CAMPAIGN_EMAIL_TO is required")
    client = TestClient(service)
    created = client.post(
        "/payments/notify",
        json={
            "payment_id": "pay-demo-1042",
            "recipient": recipient,
            "amount_minor": 12500,
            "currency": "USD",
            "risk_score": 24,
        },
    )
    created.raise_for_status()
    print(created.json())


if __name__ == "__main__":
    main()
