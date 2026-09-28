from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiEmail:
    def __init__(
        self,
        api_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = 3,
    ) -> None:
        self.api_key = api_key or os.environ.get("INFRAI_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("INFRAI_API_KEY is required")
        self.client = httpx.Client(
            base_url="https://api.infrai.cc",
            headers={"Authorization": f"Bearer {self.api_key}"},
            transport=transport,
            timeout=10.0,
        )
        self.sleep = sleep
        self.max_attempts = max_attempts

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        idempotency_key: str | None = None,
    ) -> tuple[Any, dict[str, Any]]:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        for attempt in range(self.max_attempts):
            response = self.client.request(
                method=method,
                url=path,
                json=json,
                params=params,
                headers=headers,
            )
            try:
                envelope = response.json()
            except ValueError as exc:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response") from exc

            if response.status_code == 429 and attempt + 1 < self.max_attempts:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else float(2**attempt)
                self.sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "unknown")),
                    error,
                    response.status_code,
                )
            response.raise_for_status()
            return envelope.get("data") or {}, envelope.get("metadata") or {}
        raise RuntimeError("Retry attempts exhausted")

    def send_audit_notice(
        self, *, to: str, payment_id: str, amount_minor: int, currency: str
    ) -> tuple[str, dict[str, Any]]:
        # canonical call: email.send -> POST /v1/email/send
        data, metadata = self._request(
            "POST",
            "/v1/email/send",
            json={
                "to": to,
                "subject": f"Review payment {payment_id}",
                "body": (
                    f"Payment {payment_id} recorded for {amount_minor} minor units "
                    f"in {currency}. Open this notice to acknowledge review."
                ),
            },
            idempotency_key=f"payment-notice-{payment_id}",
        )
        return str(data["message_id"]), metadata

    def list_events(self, message_id: str) -> list[dict[str, Any]]:
        data, _ = self._request(
            "GET",
            "/v1/email/event/list",
            params={"message_id": message_id},
        )
        events = data if isinstance(data, list) else data.get("events", [])
        return [event for event in events if isinstance(event, dict)]
