"""WebSocket price streaming, proxied through the backend.

The browser connects to /ws/prices and sends the Yahoo symbols it wants. The
backend opens its own connection to Twelve Data (so the API key never reaches
the browser), subscribes to the mapped symbols, and relays each price tick back
to the client keyed by the original Yahoo symbol.
"""

from __future__ import annotations

import asyncio
import json

import websockets as wslib
from fastapi import WebSocket, WebSocketDisconnect

from .config import settings
from .providers import twelvedata

TD_WS_URL = "wss://ws.twelvedata.com/v1/quotes/price"


async def stream_prices(client: WebSocket) -> None:
    await client.accept()

    if not settings.twelve_data_api_key:
        await client.close(code=1011)
        return

    try:
        init = await client.receive_json()
    except Exception:
        await client.close()
        return

    yahoo_syms = init.get("symbols", []) if isinstance(init, dict) else []
    td_map: dict[str, str] = {}
    for y in yahoo_syms:
        ts = twelvedata.td_symbol(y)
        if ts:
            td_map[ts] = y  # later wins; fine — symbols are unique enough
    if not td_map:
        await client.close()
        return

    url = f"{TD_WS_URL}?apikey={settings.twelve_data_api_key}"
    try:
        async with wslib.connect(url, open_timeout=10) as upstream:
            await upstream.send(
                json.dumps(
                    {"action": "subscribe", "params": {"symbols": ",".join(td_map.keys())}}
                )
            )

            async def pump_upstream() -> None:
                async for raw in upstream:
                    try:
                        data = json.loads(raw)
                    except Exception:
                        continue
                    if data.get("event") == "price" and data.get("price") is not None:
                        y = td_map.get(data.get("symbol"))
                        if y:
                            await client.send_json({"symbol": y, "price": data["price"]})

            async def watch_client() -> None:
                # Reading from the client lets us notice when it disconnects.
                while True:
                    await client.receive_text()

            up_task = asyncio.create_task(pump_upstream())
            cl_task = asyncio.create_task(watch_client())
            _, pending = await asyncio.wait(
                {up_task, cl_task}, return_when=asyncio.FIRST_COMPLETED
            )
            for t in pending:
                t.cancel()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        try:
            await client.close()
        except Exception:
            pass
