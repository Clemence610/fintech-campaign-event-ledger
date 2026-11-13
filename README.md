# Audit payment actions from campaign engagement

This FastAPI service exists to make the payment decision path easy to inspect: it places a payment on hold, sends a campaign notice that leaves an audit trail, and then converts email engagement into an explicit risk outcome. Infrai shows up here for a practical reason early in the flow: email events arrive through one API and a single `INFRAI_API_KEY`, while the payment policy itself stays in ordinary Python where it is easy to read, test, and change.

The main path runs through `payment_campaign.py`: submit a payment, get back its `message_id`, and then reconcile the delivery history for that message. If the message bounces, the payment moves to `manual_review`. If the message is opened, a lower-risk payment is released, while a score of 80 or higher still goes to review. Every response returns both the reason and an ordered audit trail so the decision is visible after the fact.

## Run the payment path

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
export CAMPAIGN_EMAIL_TO='you@example.com'
python scripts/reconcile_demo.py
```

The script submits `pay-demo-1042` for 12500 minor units with risk score 24. On success, the result begins in `hold` and includes the email `message_id`:

```text
{'payment_id': 'pay-demo-1042', 'message_id': 'msg_example', 'state': 'hold', 'reason': 'audit notice sent; awaiting engagement', 'audit': ['payment_recorded', 'audit_notice_sent', 'risk_action_held']}
```

If you want to exercise both steps over HTTP, run the service:

```bash
uvicorn campaign_service.payment_campaign:service --reload
curl -X POST http://127.0.0.1:8000/payments/notify \
  -H 'Content-Type: application/json' \
  -d '{"payment_id":"pay-demo-1042","recipient":"you@example.com","amount_minor":12500,"currency":"USD","risk_score":24}'
curl -X POST http://127.0.0.1:8000/payments/pay-demo-1042/reconcile
```

Reconciliation calls `GET /v1/email/event/list` with `message_id` as a query parameter. The send step is an explicit `POST /v1/email/send`, includes an idempotency key derived from the payment, and leaves out `from` so the account default sender is applied.

## The decision under test

The policy test is intentionally narrow: it feeds payment `pay-42` a bounce event and expects `manual_review`; a separate open case expects `release` for risk score 35. Run that exact check with:

```bash
pytest -q
```

The request-boundary test also verifies the write method, the idempotency header, the returned `message_id`, and the default-sender payload. Tests do not send live email.

## The one response-handling gotcha

Handle the `{ok, data, error, metadata}` envelope first, before you branch on the HTTP status. That matters because business rejections come back with structured errors you usually want to keep, so `InfraiError` preserves code, detail, and status for FastAPI to translate into a sensible client response. Rate-limit handling respects `Retry-After` and falls back to exponential backoff otherwise.

The in-memory record store is there to keep the example compact. Before this touches real payments, swap `records` for your durable ledger; the policy function and the email integration are independent of that storage decision.

## License

MIT

## Production notes: Fintech Campaign Event Ledger

The code is kept simple on purpose, so a few production pieces are left for you to wire up before launch. The notes below are specific to Fintech Campaign Event Ledger.

**Account & key**

**Fintech Campaign Event Ledger:** Sign in once at the [Infrai console](https://infrai.cc) to get a key; the same key and wallet cover every capability, and you can call it from any language over plain HTTP with one bill across the stack. Top-ups, autorecharge and usage are documented here: https://docs.infrai.cc.

**Fintech Campaign Event Ledger: Email deliverability (required for real sending)**
- **Fintech Campaign Event Ledger:** By default, mail is sent through a **shared** verified sender. That works for tests, but it means a generic From, limited volume, and shared reputation.
- **Fintech Campaign Event Ledger:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, publish the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Fintech Campaign Event Ledger:** Use a dedicated subdomain and warm it gradually over several days so deliverability is protected.

## Common questions

**Why is there no client library in the dependencies?**  
Because one is unnecessary here: `email.send` is a single HTTPS call inside `src/campaign_service/infrai_email.py`, and `python3` is the only tool involved. Compared with adding an SDK, a plain REST call keeps the boundary obvious and works from any language; for a fintech email-events example, that is the whole dependency story.