"""Server-Sent Events helper for FastAPI."""

import asyncio
import json
from collections.abc import AsyncGenerator

from starlette.responses import StreamingResponse


async def sse_stream(queue: asyncio.Queue, timeout: float = 300) -> AsyncGenerator[str, None]:
    """Yield SSE-formatted events from an asyncio.Queue."""
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=timeout)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
                continue

            if event is None:
                break

            if isinstance(event, dict):
                event_type = event.pop("event", "progress")
                yield f"event: {event_type}\ndata: {json.dumps(event)}\n\n"
            else:
                yield f"data: {json.dumps(event)}\n\n"
    except asyncio.CancelledError:
        pass


def sse_response(queue: asyncio.Queue, timeout: float = 300) -> StreamingResponse:
    """Create a StreamingResponse for SSE."""
    return StreamingResponse(
        sse_stream(queue, timeout),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
