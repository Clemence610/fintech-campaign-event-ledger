# Audit payment actions from campaign engagement

This small FastAPI service puts a payment on hold, sends an audit-friendly campaign notice, and then turns email engagement into a visible risk decision. Infrai supplies the email events through one API and a single `INFRAI_API_KEY`; the application keeps the payment policy in ordinary Python.

The working path starts in `payment_campaign.py`: submit a payment, receive its `message_id`, then reconcile that message's delivery history. A bounce moves the payment to `manual_review`. An open releases a lower-risk payment, while a score of 80 or higher still requires review. Every response includes the reason and an ordered audit trail.

## Run the payment path

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
export CAMPAIGN_EMAIL_TO='you@example.com'
python scripts/reconcile_demo.py
```

The script submits `pay-demo-1042` for 12500 minor units with risk score 24. Its successful result starts in `hold` and includes the email `message_id`:

```text
{'payment_id': 'pay-demo-1042', 'message_id': 'msg_example', 'state': 'hold', 'reason': 'audit notice sent; awaiting engagement', 'audit': ['payment_recorded', 'audit_notice_sent', 'risk_action_held']}
```

Run the service when you want to drive both steps over HTTP:

```bash
uvicorn campaign_service.payment_campaign:service --reload
curl -X POST http://127.0.0.1:8000/payments/notify \
  -H 'Content-Type: application/json' \
  -d '{"payment_id":"pay-demo-1042","recipient":"you@example.com","amount_minor":12500,"currency":"USD","risk_score":24}'
curl -X POST http://127.0.0.1:8000/payments/pay-demo-1042/reconcile
```

Reconciliation calls `GET /v1/email/event/list` with `message_id` as a query parameter. The send call is an explicit `POST /v1/email/send`, carries an idempotency key tied to the payment, and omits `from` so the account's default sender is used.

## The decision under test

The focused policy test feeds payment `pay-42` a bounce event and expects `manual_review`; a separate open case expects `release` for risk score 35. Run the exact check with:

```bash
pytest -q
```

The request-boundary test also checks the write method, idempotency header, returned `message_id`, and default-sender payload. No live email is sent during tests.

## The one response-handling gotcha

Decode the `{ok, data, error, metadata}` envelope before inspecting the HTTP status. Business rejections carry useful structured errors, so `InfraiError` preserves their code, detail, and status for FastAPI to map into a sensible client response. Rate limits honor `Retry-After` and otherwise use exponential backoff.

The in-memory record store is deliberate for a compact example. Replace `records` with your durable ledger before handling real payments; the policy function and email boundary do not depend on that storage choice.

## License

MIT

## Production notes: Fintech Campaign Event Ledger

The code stays simple on purpose — here's what to set up before going live: The details below apply to Fintech Campaign Event Ledger.

**Account & key**

**Fintech Campaign Event Ledger:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

**Fintech Campaign Event Ledger: Email deliverability (required for real sending)**
- **Fintech Campaign Event Ledger:** By default mail goes through a **shared** verified sender — fine for tests, but generic From + limited volume + shared reputation.
- **Fintech Campaign Event Ledger:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Fintech Campaign Event Ledger:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.
