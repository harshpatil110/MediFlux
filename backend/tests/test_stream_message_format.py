"""Exercise the wire format consumed by mobile EventSource message listeners."""

import asyncio
import json

import pytest

from app.events.bus import in_process_event_bus
from app.events.models import EventEnvelope
from app.events.sse import sse_event_stream


@pytest.mark.parametrize("named_events", [True, False])
async def test_replay_and_live_event_format(named_events: bool) -> None:
    """Both formats preserve topic metadata, replay cursors, and node isolation."""
    in_process_event_bus.clear()
    node_id = "11111111-1111-1111-1111-111111111111"
    for event_id in ("cursor", "replayed"):
        await in_process_event_bus.publish("pos.sales", EventEnvelope(
            event_id=event_id, type="pos.sales", node_id=node_id, payload={"quantity": 1},
        ))
    stream = sse_event_stream(
        topics=["pos.sales"], last_event_id="cursor",
        visible_nodes={node_id}, named_events=named_events,
    )
    try:
        replayed = await anext(stream)
        assert replayed.id == "replayed"
        assert replayed.event == ("pos.sales" if named_events else "message")
        assert json.loads(replayed.data)["event_type"] == "pos.sales"
        await anext(stream)  # Connected signal registers the live subscription.
        for event_id, event_node in (("hidden", "other-node"), ("live", node_id)):
            await in_process_event_bus.publish("pos.sales", EventEnvelope(
                event_id=event_id, type="pos.sales", node_id=event_node, payload={},
            ))
        live = await asyncio.wait_for(anext(stream), timeout=1)
        assert live.id == "live"
        assert live.event == replayed.event
        assert json.loads(live.data)["node_id"] == node_id
        assert b"\r\n" in live.encode()
    finally:
        await stream.aclose()
        in_process_event_bus.clear()
