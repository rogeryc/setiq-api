"""Local test harness for the Meta webhook pipeline.

Signs realistic Meta payloads with the real META_APP_SECRET, POSTs them
to /webhooks/meta on a running local backend, and reports what happened.

What this validates end-to-end:
  - Signature verification (HMAC-SHA256 against the real App Secret)
  - webhook_events row insert
  - background parser.process_event runs and lands rows in messages /
    conversations (depending on the payload shape)

No public URL required, no Meta involvement. Pure dev tooling.

Usage:
    # Start the API first: .venv/bin/uvicorn setiq.main:app --port 8000
    uv run python scripts/test_meta_webhook.py
    # Or run a single payload:
    uv run python scripts/test_meta_webhook.py ig_comment
"""
import asyncio
import hashlib
import hmac
import json
import sys
from pathlib import Path
from typing import Any

import asyncpg
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from setiq.config import settings  # noqa: E402

WEBHOOK_URL = "http://localhost:8000/webhooks/meta"

# Thalma's seeded IG Business + Page IDs — the parser uses these to look
# up the tenant in `tenants.settings.meta.{instagram_business_ids|page_ids}`.
IG_BUSINESS_ID = "17841400000000000"
PAGE_ID = "100000000000001"


# ---- Fixtures: real-shape Meta webhook payloads ----------------------------

FIXTURES: dict[str, dict[str, Any]] = {
    "ig_comment": {
        "object": "instagram",
        "entry": [
            {
                "id": IG_BUSINESS_ID,
                "time": 1748000000,
                "changes": [
                    {
                        "field": "comments",
                        "value": {
                            "id": "comment_test_001",
                            "from": {"id": "12345678", "username": "test_user_harness"},
                            "media": {"id": "media_test_001", "media_product_type": "FEED"},
                            "text": "Test comment desde el harness local",
                            "parent_id": None,
                        },
                    }
                ],
            }
        ],
    },
    "ig_dm": {
        "object": "instagram",
        "entry": [
            {
                "id": IG_BUSINESS_ID,
                "time": 1748000010,
                "messaging": [
                    {
                        "sender": {"id": "ig_user_777"},
                        "recipient": {"id": IG_BUSINESS_ID},
                        "timestamp": 1748000010000,
                        "message": {
                            "mid": "dm_test_001",
                            "text": "Hola, te escribo por DM desde el harness",
                        },
                    }
                ],
            }
        ],
    },
    "fb_comment": {
        "object": "page",
        "entry": [
            {
                "id": PAGE_ID,
                "time": 1748000020,
                "changes": [
                    {
                        "field": "feed",
                        "value": {
                            "item": "comment",
                            "verb": "add",
                            "comment_id": "fb_comment_test_001",
                            "post_id": "fb_post_test_001",
                            "sender_id": "fb_user_555",
                            "sender_name": "Test FB User",
                            "message": "Comentario FB desde el harness",
                        },
                    }
                ],
            }
        ],
    },
    "fb_messenger": {
        "object": "page",
        "entry": [
            {
                "id": PAGE_ID,
                "time": 1748000030,
                "messaging": [
                    {
                        "sender": {"id": "fb_user_888"},
                        "recipient": {"id": PAGE_ID},
                        "timestamp": 1748000030000,
                        "message": {
                            "mid": "messenger_test_001",
                            "text": "Mensaje desde Messenger via harness",
                        },
                    }
                ],
            }
        ],
    },
}


def sign(body: bytes) -> str:
    """Compute X-Hub-Signature-256 header value: 'sha256=<hex_hmac>'."""
    digest = hmac.new(
        settings.meta_app_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}"


async def post_fixture(name: str, payload: dict[str, Any]) -> None:
    body = json.dumps(payload).encode()
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": sign(body),
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(WEBHOOK_URL, content=body, headers=headers)
    ok = "✓" if resp.status_code == 200 else "✗"
    print(f"  {ok} {name:<14} status={resp.status_code} body={resp.text[:140]}")


async def post_bad_signature(name: str = "bad_sig") -> None:
    """Sanity check: a request with a tampered signature must return 401."""
    body = json.dumps({"object": "instagram", "entry": []}).encode()
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": "sha256=" + "0" * 64,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(WEBHOOK_URL, content=body, headers=headers)
    ok = "✓" if resp.status_code == 401 else "✗"
    print(f"  {ok} {name:<14} status={resp.status_code} (expected 401)")


async def report_db_state() -> None:
    """Print what landed after the webhook events were processed."""
    conn = await asyncpg.connect(settings.database_url)
    try:
        events = await conn.fetch(
            """
            SELECT status, COUNT(*) AS n
            FROM webhook_events
            WHERE source = 'meta'
            GROUP BY status
            ORDER BY status
            """
        )
        print("\nwebhook_events totals (all-time):")
        for r in events:
            print(f"  {r['status']:<10} {r['n']}")
        recent_msgs = await conn.fetchval(
            "SELECT COUNT(*) FROM messages WHERE external_id LIKE 'comment_test_%' OR external_id LIKE 'dm_test_%' OR external_id LIKE 'fb_%_test_%' OR external_id LIKE 'messenger_test_%'"
        )
        print(f"\nharness-created messages landed: {recent_msgs}")
    finally:
        await conn.close()


async def main() -> None:
    if not settings.meta_app_secret or settings.meta_app_secret.startswith(("dev_", "ROTATE")):
        print("⚠  META_APP_SECRET is unset / dev placeholder — set the real value in .env first.")
        sys.exit(1)

    targets = sys.argv[1:] or list(FIXTURES.keys())
    bad = [t for t in targets if t not in FIXTURES and t != "bad_sig"]
    if bad:
        print(f"unknown fixture(s): {bad}. Available: {', '.join(FIXTURES.keys())}, bad_sig")
        sys.exit(1)

    print(f"POSTing fixtures to {WEBHOOK_URL}\n")
    for name in targets:
        if name == "bad_sig":
            await post_bad_signature()
        else:
            await post_fixture(name, FIXTURES[name])

    # Give the background task a moment before checking DB state.
    await asyncio.sleep(0.6)
    await report_db_state()


if __name__ == "__main__":
    asyncio.run(main())
