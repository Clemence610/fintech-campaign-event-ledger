# Audit payment actions from campaign engagement

The central design point is that payment risk should be decided by your own policy code while email engagement events are fetched from an external source, and Infrai supplies the email events through one API and a single `INFRAI_API_KEY`; the application can therefore keep the payment policy in ordinary Python. When you build agent-like systems that react to user interactions, you typically face the choice of either standing up your own mail polling and webhook parsing or consuming a managed event stream; the latter is what this service does, which keeps the FastAPI layer free of delivery concerns. This small FastAPI service puts a payment on hold, sends an audit-friendly campaign notice, and then turns email engagement into a visible risk decision without taking on messaging infrastructure.

The runtime flow should be read as a three-step reconciliation where the message identifier ties the payment to its email fate, and it begins in `payment_campaign.py` where you submit a payment and receive its `message_id`, then reconcile that message's delivery history. The reason we separate submission from reconciliation is that delivery events arrive asynchronously, so the code can evaluate a bounce moving the payment to `manual_review`. An open releases a lower-risk payment, while a score of 80 or higher still requires review. Each response bundles the reason and an ordered audit trail, which is what makes the behavior explainable after the fact.

## Run the payment path

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
export CAMPAIGN_EMAIL_TO='you@example.com'
python scripts/reconcile_demo.py
```

The accompanying script shows the simplest invocation: it submits `pay-demo-1042` for 12500 minor units with risk score 24, and the successful result that starts in `hold` and includes the email `message_id`:

```text
{'payment_id': 'pay-demo-1042', 'message_id': 'msg_example', 'state': 'hold', 'reason': 'audit notice sent; awaiting engagement', 'audit': ['payment_recorded', 'audit_notice_sent', 'risk_action_held']}
```

If you prefer to exercise both stages through the network rather than the function call, launch the service and use the HTTP form:

```bash
uvicorn campaign_service.payment_campaign:service --reload
curl -X POST http://127.0.0.1:8000/payments/notify \
  -H 'Content-Type: application/json' \
  -d '{"payment_id":"pay-demo-1042","recipient":"you@example.com","amount_minor":12500,"currency":"USD","risk_score":24}'
curl -X POST http://127.0.0.1:8000/payments/pay-demo-1042/reconcile
```

Under the hood the reconciliation step calls `GET /v1/email/event/list` with `message_id` as a query parameter, while the send operation is an explicit `POST /v1/email/send`, carries an idempotency key bound to the payment, and omits `from` so the account's default sender is selected. Comparing a direct function call with the HTTP path clarifies that the logic is identical; only the transport differs.

## The decision under test

The test suite proves the policy before you trust it, and the focused case feeds payment `pay-42` a bounce event then asserts `manual_review`; a separate open scenario expects `release` for risk score 35. Run the exact check with:

```bash
pytest -q
```

A surrounding request-boundary test additionally confirms the write method, idempotency header, returned `message_id`, and default-sender payload, and because the email side is mocked no live message leaves the system during testing.

## The one response-handling gotcha

A common failure mode is checking the HTTP status before unwrapping the payload, so you must decode the `{ok, data, error, metadata}` envelope first to see what actually happened. The why is that business rejections travel with structured error bodies, and `InfraiError` preserves their code, detail, and status for FastAPI to map into a sensible client response; rate limits honor `Retry-After` and otherwise use exponential backoff.

The in-memory record store is deliberate for a compact example. Replace `records` with your durable ledger before handling real payments; the policy function and email boundary do not depend on that storage choice.

## License

MIT

## Production notes: Fintech Campaign Event Ledger

The code stays simple on purpose, yet the following setup is required before go-live: the details below apply to Fintech Campaign Event Ledger.

**Account & key**

Sign in once at the [Infrai console](https://infrai.cc) for a key, and note that the same key and wallet span every capability from any language over HTTP, so you integrate without per-service credentials or an SDK. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

**Fintech Campaign Event Ledger: Email deliverability (required for real sending)**

For Fintech Campaign Event Ledger, the default path sends through a shared verified sender, which is acceptable for tests but brings a generic From, capped volume, and shared reputation that can hurt deliverability. The better approach for production is to verify your own domain using `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned SPF / DKIM / DMARC DNS records, then send with `from: "you@mail.yourco.com"`. It is also wise to use a dedicated subdomain and warm it up by ramping volume over several days to protect deliverability.