"""Inbound attribution on a *shared* WhatsApp number.

Four Quata products send from one "QUATA" engagement number, and
``uq_whatsapp_conversations_account_contact`` means one customer is one
conversation row across all four. An inbound reply on that row is therefore
genuinely ambiguous, and the two heuristics that came before were both
guesses that a product could steer:

* **first touch** — pre-claim a guessable phone number with one cheap
  utility send and own every reply that customer ever sends;
* **last touch** — no race needed at all. One message, at will, repeatedly,
  and the previous owner also lost the thread it had already been served.

What this module pins instead:

1. ``context.id`` (Meta's own threading) decides when it is present, and it
   beats "who sent last" — a wamid exists only because we sent that message.
2. With no context, only a single-candidate thread is answered. Two products
   inside the service window means the reply goes to **nobody** and is
   reported as a denial for a human to resolve.
3. Attribution never retracts. A product that has already been served a
   thread keeps it when another product sends.
4. Sending never takes an owned thread.

Plus the two properties that predate this and must not regress: a send by
one product never enters another's history, and no accepted send is left
with ``conversation_id IS NULL``.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.db.session import SessionLocal
from app.models import (
    WhatsAppAccount,
    WhatsAppAuditLog,
    WhatsAppConversation,
    WhatsAppMessage,
    WhatsAppProduct,
)
from app.services.whatsapp import conversations as conv
from app.services.whatsapp.credentials import encrypt_wa_secret


APP_SECRET = "pytest-attrib-secret-4d1e"
PHONE_NUMBER_ID = "PNID-PYTEST-ATTRIB"
DISPLAY_PHONE = "+237600009999"


# ---------------------------------------------------------------------------
# World
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def world(app_instance):
    """One inactive engagement account and three products.

    Inactive on purpose — the webhook accepts traffic for an account that is
    not live yet, and staying inactive keeps this row clear of the partial
    unique index that allows one active account per purpose, so this module
    cannot collide with any other test module's world.
    """
    from fastapi.testclient import TestClient

    suffix = uuid.uuid4().hex[:8]
    slug = f"pytest-attrib-{suffix}"
    with TestClient(app_instance):  # lifespan → create_all
        with SessionLocal() as db:
            account = WhatsAppAccount(
                slug=slug,
                name="Pytest Shared Engagement",
                purpose="engagement",
                phone_number_id=f"{PHONE_NUMBER_ID}-{suffix}",
                waba_id=f"WABA-ATTRIB-{suffix}",
                display_phone=DISPLAY_PHONE,
                app_secret_encrypted=encrypt_wa_secret(APP_SECRET),
                is_active=False,
            )
            db.add(account)
            db.flush()
            products = {}
            for name in ("alpha", "beta", "gamma"):
                row = WhatsAppProduct(
                    slug=f"attrib_{name}_{suffix}",
                    name=f"Attrib {name.title()}",
                    is_enabled=True,
                    api_key_hash=hashlib.sha256(f"{name}{suffix}".encode()).hexdigest(),
                    api_key_prefix=f"qcp_at_{name[:3]}",
                    allowed_purposes=["engagement"],
                    default_locale="en",
                )
                db.add(row)
                db.flush()
                products[name] = row.id
            db.commit()
            return {
                "slug": slug,
                "suffix": suffix,
                "account_id": account.id,
                "phone_number_id": account.phone_number_id,
                **products,
            }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _thread(db, world, *, phone: str, owner_id=None) -> WhatsAppConversation:
    row = WhatsAppConversation(
        account_id=world["account_id"],
        product_id=owner_id,
        wa_contact_id=conv.wa_contact_id_for(phone),
        phone_e164=phone,
        state="open",
    )
    db.add(row)
    db.flush()
    return row


def _outbound(
    db,
    world,
    conversation,
    *,
    product_id: int,
    status: str = "queued",
    wamid: str | None = None,
    created_at: datetime | None = None,
) -> WhatsAppMessage:
    row = WhatsAppMessage(
        message_uid=uuid.uuid4().hex[:32],
        account_id=world["account_id"],
        account_purpose="engagement",
        conversation_id=conversation.id,
        product_id=product_id,
        direction="outbound",
        # "text", not "template": a template row needs a real template_id
        # (``ck_whatsapp_messages_template_required``) and none of these
        # tests turn on the template invariant, which
        # ``test_whatsapp_invariant`` owns.
        kind="text",
        template_id=None,
        to_phone_e164=conversation.phone_e164,
        provider_message_id=wamid,
        status=status,
    )
    if created_at is not None:
        row.created_at = created_at
        row.updated_at = created_at
    db.add(row)
    db.flush()
    return row


def _phone() -> str:
    return "+2376" + uuid.uuid4().int.__str__()[:8]


def _envelope(world, *, wa_id: str, text: str, wamid: str, context_id: str | None = None):
    message = {
        "from": wa_id,
        "id": wamid,
        "timestamp": str(int(datetime.now(timezone.utc).timestamp())),
        "type": "text",
        "text": {"body": text},
    }
    if context_id is not None:
        message["context"] = {"from": DISPLAY_PHONE.lstrip("+"), "id": context_id}
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": f"WABA-ATTRIB-{world['suffix']}",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": DISPLAY_PHONE,
                                "phone_number_id": world["phone_number_id"],
                            },
                            "messages": [message],
                        },
                    }
                ],
            }
        ],
    }


def _post_inbound(client, world, *, phone: str, text="where is it?", context_id=None):
    wamid = f"wamid.ATTRIB{uuid.uuid4().hex.upper()}"
    raw = json.dumps(
        _envelope(
            world, wa_id=phone.lstrip("+"), text=text, wamid=wamid, context_id=context_id
        ),
        separators=(",", ":"),
    ).encode("utf-8")
    signature = "sha256=" + hmac.new(APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    r = client.post(
        f"/api/v1/whatsapp/webhook/{world['slug']}",
        content=raw,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": signature},
    )
    return r, wamid


def _inbound_row(wamid: str) -> WhatsAppMessage:
    with SessionLocal() as db:
        return (
            db.query(WhatsAppMessage)
            .filter(WhatsAppMessage.provider_message_id == wamid)
            .one()
        )


# ---------------------------------------------------------------------------
# 1 — Meta's own threading decides, and it beats last-touch
# ---------------------------------------------------------------------------

def test_reply_with_context_goes_to_the_product_that_sent_that_message(client, world):
    """``context.id`` is the wamid of the message being answered.

    Beta writes *after* Alpha, so every "who sent last" rule hands Beta the
    reply. But the customer replied to Alpha's message, and a wamid only
    exists because Meta gave it to us for Alpha's send — Beta cannot
    manufacture it. Context wins.
    """
    phone = _phone()
    alpha_wamid = f"wamid.ALPHA{uuid.uuid4().hex.upper()}"
    with SessionLocal() as db:
        thread = _thread(db, world, phone=phone)
        _outbound(db, world, thread, product_id=world["alpha"], wamid=alpha_wamid)
        _outbound(db, world, thread, product_id=world["beta"])
        db.commit()

    r, wamid = _post_inbound(client, world, phone=phone, context_id=alpha_wamid)
    assert r.status_code == 200, r.text
    assert _inbound_row(wamid).product_id == world["alpha"]


def test_context_pointing_at_another_thread_is_not_honoured(client, world):
    """A wamid from a different conversation proves nothing about this one.

    Falls through to the no-context rules — here, one addressee — rather
    than importing another thread's owner.
    """
    phone, other_phone = _phone(), _phone()
    foreign_wamid = f"wamid.FOREIGN{uuid.uuid4().hex.upper()}"
    with SessionLocal() as db:
        elsewhere = _thread(db, world, phone=other_phone)
        _outbound(db, world, elsewhere, product_id=world["gamma"], wamid=foreign_wamid)
        thread = _thread(db, world, phone=phone)
        _outbound(db, world, thread, product_id=world["beta"])
        db.commit()

    r, wamid = _post_inbound(client, world, phone=phone, context_id=foreign_wamid)
    assert r.status_code == 200, r.text
    assert _inbound_row(wamid).product_id == world["beta"]


# ---------------------------------------------------------------------------
# 2 — no context: one candidate, or nobody
# ---------------------------------------------------------------------------

def test_reply_with_no_context_and_two_addressees_goes_to_nobody(client, world):
    """The reproduced attack, and the reason neither heuristic is sound.

    Beta sends one cheap message to a guessable number that Alpha is working
    and, under last-touch, reads the customer's next reply. Under
    first-touch, Alpha reads a reply that may well be for Beta. Both are
    disclosure of one company's customer message to another. Nobody gets it.
    """
    phone = _phone()
    with SessionLocal() as db:
        thread = _thread(db, world, phone=phone, owner_id=world["alpha"])
        _outbound(db, world, thread, product_id=world["alpha"])
        _outbound(db, world, thread, product_id=world["beta"])
        db.commit()
        thread_id = thread.id

    r, wamid = _post_inbound(client, world, phone=phone, text="my order is late")
    assert r.status_code == 200, r.text

    row = _inbound_row(wamid)
    assert row.product_id is None
    # Still on the thread — the admin console reads it unscoped.
    assert row.conversation_id == thread_id
    assert row.body == "my order is late"

    # And an operator is told, where the console already looks.
    with SessionLocal() as db:
        denial = (
            db.query(WhatsAppAuditLog)
            .filter(
                WhatsAppAuditLog.action == "conversation.inbound_unattributed",
                WhatsAppAuditLog.resource_id == str(thread_id),
            )
            .one()
        )
        assert denial.outcome == "denied"
        assert denial.reason == "ambiguous_inbound"


def test_ambiguity_does_not_leak_into_either_products_history(client, world):
    phone = _phone()
    with SessionLocal() as db:
        thread = _thread(db, world, phone=phone, owner_id=world["alpha"])
        _outbound(db, world, thread, product_id=world["alpha"])
        _outbound(db, world, thread, product_id=world["beta"])
        db.commit()
        thread_id = thread.id

    _post_inbound(client, world, phone=phone)

    with SessionLocal() as db:
        thread = db.get(WhatsAppConversation, thread_id)
        for key in ("alpha", "beta", "gamma"):
            rows = conv.history(db, thread, product_id=world[key])
            assert [r.direction for r in rows].count("inbound") == 0, key
        # The console, which passes no product scope, sees all three.
        assert len(conv.history(db, thread)) == 3


def test_sole_addressee_in_the_window_keeps_the_reply(client, world):
    phone = _phone()
    with SessionLocal() as db:
        thread = _thread(db, world, phone=phone, owner_id=world["alpha"])
        _outbound(db, world, thread, product_id=world["alpha"])
        db.commit()

    r, wamid = _post_inbound(client, world, phone=phone)
    assert r.status_code == 200, r.text
    assert _inbound_row(wamid).product_id == world["alpha"]


def test_a_suppressed_send_is_not_addressing_the_contact(client, world):
    """A suppressed message never left, so the customer cannot be replying
    to it — and it must not make an otherwise-clear thread ambiguous."""
    phone = _phone()
    with SessionLocal() as db:
        thread = _thread(db, world, phone=phone)
        _outbound(db, world, thread, product_id=world["alpha"])
        _outbound(db, world, thread, product_id=world["beta"], status="suppressed")
        db.commit()

    r, wamid = _post_inbound(client, world, phone=phone)
    assert r.status_code == 200, r.text
    assert _inbound_row(wamid).product_id == world["alpha"]


def test_a_cold_inbound_belongs_to_nobody(client, world):
    """Nobody has messaged this contact, so nobody is owed the reply — and
    the thread stays unowned rather than being handed to whoever asks."""
    phone = _phone()
    r, wamid = _post_inbound(client, world, phone=phone, text="hello?")
    assert r.status_code == 200, r.text

    row = _inbound_row(wamid)
    assert row.product_id is None
    with SessionLocal() as db:
        assert db.get(WhatsAppConversation, row.conversation_id).product_id is None


def test_a_stale_single_product_thread_still_gets_its_reply(client, world):
    """One product, one thread, an update three days old.

    Nobody addressed the contact inside the 24h window, but there is exactly
    one candidate in the whole thread — that is not a tie-break, it is the
    ordinary single-product case, and stranding it would be a regression
    with no security value.
    """
    phone = _phone()
    long_ago = datetime.now(timezone.utc) - timedelta(days=3)
    with SessionLocal() as db:
        thread = _thread(db, world, phone=phone, owner_id=world["gamma"])
        _outbound(db, world, thread, product_id=world["gamma"], created_at=long_ago)
        db.commit()

    r, wamid = _post_inbound(client, world, phone=phone)
    assert r.status_code == 200, r.text
    assert _inbound_row(wamid).product_id == world["gamma"]


def test_two_stale_products_are_still_ambiguous(client, world):
    phone = _phone()
    long_ago = datetime.now(timezone.utc) - timedelta(days=3)
    with SessionLocal() as db:
        thread = _thread(db, world, phone=phone, owner_id=world["alpha"])
        _outbound(db, world, thread, product_id=world["alpha"], created_at=long_ago)
        _outbound(db, world, thread, product_id=world["beta"], created_at=long_ago)
        db.commit()

    r, wamid = _post_inbound(client, world, phone=phone)
    assert r.status_code == 200, r.text
    assert _inbound_row(wamid).product_id is None


def test_thread_owner_alone_does_not_earn_the_reply(client, world):
    """Ownership is a claim on the thread, not evidence about a message.

    A product that owns a thread but has sent nothing on it (adopted it, or
    was seeded there) must not collect a stranger's inbound.
    """
    phone = _phone()
    with SessionLocal() as db:
        _thread(db, world, phone=phone, owner_id=world["alpha"])
        db.commit()

    r, wamid = _post_inbound(client, world, phone=phone)
    assert r.status_code == 200, r.text
    assert _inbound_row(wamid).product_id is None


# ---------------------------------------------------------------------------
# 3 + 4 — attribution never retracts, sending never takes
# ---------------------------------------------------------------------------

def test_a_send_never_takes_an_owned_thread(world):
    phone = _phone()
    with SessionLocal() as db:
        thread = _thread(db, world, phone=phone, owner_id=world["alpha"])
        db.commit()
        thread_id = thread.id

    with SessionLocal() as db:
        thread = db.get(WhatsAppConversation, thread_id)
        beta = db.get(WhatsAppProduct, world["beta"])
        row = _outbound(db, world, thread, product_id=beta.id)
        row.conversation_id = None
        db.commit()
        uid = row.message_uid

    with SessionLocal() as db:
        beta = db.get(WhatsAppProduct, world["beta"])
        conv.attach_outbound(db, product=beta, message_uid=uid, phone_e164=phone)
        db.commit()
        assert db.get(WhatsAppConversation, thread_id).product_id == world["alpha"]


def test_an_unowned_thread_is_adopted_by_the_first_sender(world):
    phone = _phone()
    with SessionLocal() as db:
        thread = _thread(db, world, phone=phone)
        beta = db.get(WhatsAppProduct, world["beta"])
        row = _outbound(db, world, thread, product_id=beta.id)
        row.conversation_id = None
        db.commit()
        thread_id, uid = thread.id, row.message_uid

    with SessionLocal() as db:
        beta = db.get(WhatsAppProduct, world["beta"])
        conv.attach_outbound(db, product=beta, message_uid=uid, phone_e164=phone)
        db.commit()
        assert db.get(WhatsAppConversation, thread_id).product_id == world["beta"]


def test_a_product_keeps_a_thread_after_another_product_sends(world):
    """The retroactive loss the reviewer reproduced.

    Under last-touch, Beta's send flipped ``product_id`` and Alpha started
    404-ing on a thread it had been reading a second earlier — losing access
    to its own already-delivered messages. Deciding who gets the *next*
    inbound must not retract what a product already has.
    """
    phone = _phone()
    with SessionLocal() as db:
        thread = _thread(db, world, phone=phone, owner_id=world["alpha"])
        _outbound(db, world, thread, product_id=world["alpha"])
        db.commit()
        thread_id = thread.id

    with SessionLocal() as db:
        thread = db.get(WhatsAppConversation, thread_id)
        beta = db.get(WhatsAppProduct, world["beta"])
        row = _outbound(db, world, thread, product_id=beta.id)
        row.conversation_id = None
        db.commit()
        uid = row.message_uid

    with SessionLocal() as db:
        beta = db.get(WhatsAppProduct, world["beta"])
        conv.attach_outbound(db, product=beta, message_uid=uid, phone_e164=phone)
        db.commit()

    with SessionLocal() as db:
        alpha = db.get(WhatsAppProduct, world["alpha"])
        beta = db.get(WhatsAppProduct, world["beta"])
        assert conv.for_product(db, product=alpha, conversation_id=thread_id) is not None
        assert conv.for_product(db, product=beta, conversation_id=thread_id) is not None
        assert thread_id in {
            r.id for r in conv.list_for_product(db, product=alpha, phone_e164=phone)
        }
        assert thread_id in {
            r.id for r in conv.list_for_product(db, product=beta, phone_e164=phone)
        }


def test_a_product_that_has_never_touched_a_thread_cannot_reach_it(world):
    """The widening in ``for_product`` is evidence-based, not open."""
    phone = _phone()
    with SessionLocal() as db:
        thread = _thread(db, world, phone=phone, owner_id=world["alpha"])
        _outbound(db, world, thread, product_id=world["alpha"])
        db.commit()
        thread_id = thread.id

    with SessionLocal() as db:
        gamma = db.get(WhatsAppProduct, world["gamma"])
        assert conv.for_product(db, product=gamma, conversation_id=thread_id) is None
        assert conv.list_for_product(db, product=gamma, phone_e164=phone) == []


def test_an_unattributed_thread_is_invisible_to_every_product(world):
    phone = _phone()
    with SessionLocal() as db:
        thread = _thread(db, world, phone=phone)
        db.commit()
        thread_id = thread.id

    with SessionLocal() as db:
        for key in ("alpha", "beta", "gamma"):
            product = db.get(WhatsAppProduct, world[key])
            assert conv.for_product(db, product=product, conversation_id=thread_id) is None


# ---------------------------------------------------------------------------
# Regression guards — properties that predate this change
# ---------------------------------------------------------------------------

def test_a_shared_thread_still_does_not_share_messages(world):
    phone = _phone()
    with SessionLocal() as db:
        thread = _thread(db, world, phone=phone, owner_id=world["alpha"])
        mine = _outbound(db, world, thread, product_id=world["alpha"])
        theirs = _outbound(db, world, thread, product_id=world["beta"])
        db.commit()
        thread_id, mine_uid, theirs_uid = thread.id, mine.message_uid, theirs.message_uid

    with SessionLocal() as db:
        thread = db.get(WhatsAppConversation, thread_id)
        alpha_uids = {
            r.message_uid for r in conv.history(db, thread, product_id=world["alpha"])
        }
        assert mine_uid in alpha_uids
        assert theirs_uid not in alpha_uids


def test_an_accepted_send_is_never_left_without_a_conversation(world):
    phone = _phone()
    with SessionLocal() as db:
        thread = _thread(db, world, phone=phone, owner_id=world["alpha"])
        beta = db.get(WhatsAppProduct, world["beta"])
        row = _outbound(db, world, thread, product_id=beta.id)
        row.conversation_id = None
        db.commit()
        uid = row.message_uid

    with SessionLocal() as db:
        beta = db.get(WhatsAppProduct, world["beta"])
        conv.attach_outbound(db, product=beta, message_uid=uid, phone_e164=phone)
        db.commit()

    with SessionLocal() as db:
        assert (
            db.query(WhatsAppMessage)
            .filter(WhatsAppMessage.message_uid == uid)
            .one()
            .conversation_id
            is not None
        )


def test_service_window_stays_monotonic_and_clamped(world):
    """Untouched by this change and load-bearing: an out-of-order Meta
    redelivery must not drag the deadline backwards, and a skewed future
    timestamp must not open the free-form gate past the real 24h."""
    now = datetime.now(timezone.utc)
    phone = _phone()
    with SessionLocal() as db:
        thread = _thread(db, world, phone=phone, owner_id=world["alpha"])
        db.commit()

        conv.touch_inbound(db, thread, at=now, now=now)
        deadline = conv._as_aware(thread.service_window_expires_at)
        assert deadline == now + conv.SERVICE_WINDOW

        # Backwards: an old redelivery.
        conv.touch_inbound(db, thread, at=now - timedelta(days=900), now=now)
        assert conv._as_aware(thread.service_window_expires_at) == deadline
        assert conv._as_aware(thread.last_inbound_at) == now

        # Forwards: a skewed timestamp is clamped to now.
        conv.touch_inbound(db, thread, at=now + timedelta(days=400), now=now)
        assert conv._as_aware(thread.service_window_expires_at) == deadline
        db.rollback()
