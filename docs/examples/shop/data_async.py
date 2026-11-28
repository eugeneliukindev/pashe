"""What the examples of the shop leave out, on the async side: its database and the APIs it calls."""

import aiosqlite
import httpx

from examples.shop.data_sync import RATES, SCHEMA

queries: list[str] = []  # every statement the database ran, for the tests
partner_calls: list[str] = []  # every path the partner was asked, for the tests

db = aiosqlite.connect(":memory:")  # opened by start, in the loop that runs the example
_opened: set[aiosqlite.Connection] = set()


async def start() -> None:
    if db in _opened:
        return  # a test opened it before the calls of a page run
    opened = await db  # starts the thread of the connection
    _opened.add(opened)
    await opened.executescript(SCHEMA)
    await opened.set_trace_callback(queries.append)


async def _partner(request: httpx.Request) -> httpx.Response:
    partner_calls.append(request.url.path)
    currency = request.url.path.rsplit("/", 1)[-1]
    if currency not in RATES:
        return httpx.Response(httpx.codes.NOT_FOUND)
    return httpx.Response(httpx.codes.OK, json={"rate": RATES[currency]})


async def _payments(request: httpx.Request) -> httpx.Response:
    del request
    return httpx.Response(httpx.codes.OK, json={"access_token": "a token", "expires_in": 3600})


partner = httpx.AsyncClient(base_url="https://partner.example", transport=httpx.MockTransport(_partner))
payments = httpx.AsyncClient(base_url="https://payments.example", transport=httpx.MockTransport(_payments))


async def close() -> None:
    if db in _opened:  # its thread holds the run open until it stops
        _opened.discard(db)
        await db.close()
    await partner.aclose()
    await payments.aclose()
