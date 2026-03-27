"""Backfill dispatcher — routes SQS backfill messages to handlers."""

import importlib


_HANDLERS = {
    "backfill:parquet": "backfill.parquet",
    "backfill:raster_meta": "backfill.raster_meta",
    "backfill:regzip": "backfill.regzip",
    "backfill:temp_stats": "backfill.temp_stats",
}


def dispatch(body):
    """Route an SQS backfill message to the correct handler module."""
    msg_type = body.get("type", "")
    handler_module = _HANDLERS.get(msg_type)
    if not handler_module:
        raise ValueError(f"Unknown backfill type: {msg_type}")
    mod = importlib.import_module(handler_module)
    mod.handle(body)
