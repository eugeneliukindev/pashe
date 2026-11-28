"""What the examples of the shop leave out, on the sync side: its database and the APIs it calls."""

import sqlite3

import httpx

SCHEMA = """
CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, category TEXT, price_cents INTEGER);
CREATE TABLE orders (id INTEGER PRIMARY KEY, day TEXT, total_cents INTEGER);
INSERT INTO products VALUES (1, 'Coffee beans', 'coffee', 1290), (2, 'Espresso cups', 'coffee', 1500),
    (3, 'Green tea', 'tea', 700);
INSERT INTO orders (day, total_cents) VALUES ('2026-11-21', 2580), ('2026-11-21', 700);
"""
RATES = {"EUR": 0.92, "GBP": 0.79}  # what the partner knows

queries: list[str] = []  # every statement the database ran, for the tests
partner_calls: list[str] = []  # every path the partner was asked, for the tests

db = sqlite3.connect(":memory:", check_same_thread=False)  # the threads of the cache read it too
db.executescript(SCHEMA)
db.set_trace_callback(queries.append)


def _partner(request: httpx.Request) -> httpx.Response:
    partner_calls.append(request.url.path)
    currency = request.url.path.rsplit("/", 1)[-1]
    if currency not in RATES:
        return httpx.Response(httpx.codes.NOT_FOUND)
    return httpx.Response(httpx.codes.OK, json={"rate": RATES[currency]})


def _payments(request: httpx.Request) -> httpx.Response:
    del request
    return httpx.Response(httpx.codes.OK, json={"access_token": "a token", "expires_in": 3600})


partner = httpx.Client(base_url="https://partner.example", transport=httpx.MockTransport(_partner))
payments = httpx.Client(base_url="https://payments.example", transport=httpx.MockTransport(_payments))


def close() -> None:
    db.close()
    partner.close()
    payments.close()
