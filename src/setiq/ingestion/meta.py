"""Meta webhook ingestion: GET handshake + signed POST receive.

Meta's webhook protocol:
- GET with hub.mode=subscribe&hub.challenge=<n>&hub.verify_token=<t> — we
  must respond with the challenge body if the token matches.
- POST with JSON body and X-Hub-Signature-256: sha256=<hex>, where the hex
  is HMAC-SHA256 of the raw body using the app secret. We must verify the
  signature, persist the raw payload (for replay/debug), and return 200
  fast. Actual parsing into messages/conversations happens in a background
  worker (next iteration).
"""
import hashlib
import hmac
import json
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request, status

from setiq import db
from setiq.config import settings
from setiq.ingestion import parser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/meta", tags=["webhooks"])


def _verify_signature(body: bytes, signature_header: str | None) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(
        settings.meta_app_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    received = signature_header.split("=", 1)[1]
    return hmac.compare_digest(expected, received)


@router.get("")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_challenge: str = Query(alias="hub.challenge"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
) -> int:
    """Meta GET handshake. Echo `hub.challenge` if the verify token matches."""
    if hub_mode != "subscribe" or hub_verify_token != settings.meta_webhook_verify_token:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Verification failed")
    return int(hub_challenge)


@router.post("", status_code=status.HTTP_200_OK)
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(default=None),
) -> dict[str, str]:
    """Meta POST event. Verify signature, persist raw to webhook_events,
    return 200 fast. A worker (separate process, TBD) drains webhook_events
    rows with status='pending' into the message/conversation tables."""
    body = await request.body()
    if not _verify_signature(body, x_hub_signature_256):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid JSON: {e}") from e

    # Generate the event id app-side so we don't need RETURNING. The
    # webhook_events USING policy filters out NULL-tenant rows, which would
    # make a RETURNING clause invisible to the writer even though the row
    # was inserted successfully. The worker resolves the tenant from the
    # Page/IG ID inside the payload and backfills tenant_id later.
    event_id = uuid.uuid4()
    async with db.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO webhook_events (id, source, external_id, payload, status)
            VALUES ($1, 'meta', $2, $3, 'pending')
            """,
            event_id,
            payload.get("object"),
            payload,
        )
    background_tasks.add_task(parser.process_event, event_id)
    return {"status": "received", "event_id": str(event_id)}
