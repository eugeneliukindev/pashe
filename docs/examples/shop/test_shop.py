from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

import httpx
import pytest
from tests.harness.helpers import call

from pashe.errors import NotFoundError, RateLimitedError

if TYPE_CHECKING:
    from types import ModuleType


class Shop:
    """The modules of one side of the shop, and the queries its database ran."""

    def __init__(self, side: str) -> None:
        self.side = side

        self.data = importlib.import_module(f"examples.shop.data_{side}")

    def section(self, name: str) -> ModuleType:
        return importlib.import_module(f"examples.shop.{name}_{self.side}")

    def selects(self) -> list[str]:
        return [query for query in self.data.queries if query.startswith("SELECT")]


@pytest.fixture(params=["sync", "async"])
async def shop(request: pytest.FixtureRequest) -> Shop:
    opened = Shop(request.param)
    if opened.side == "async":
        await opened.data.start()
    return opened  # fresh_examples closes the database


async def test_a_product_is_read_from_the_database_once(shop: Shop) -> None:
    get_product = shop.section("slow_query").get_product

    first = await call(get_product, 1)
    second = await call(get_product, 1)

    assert first == second
    assert first.name == "Coffee beans"
    assert len(shop.selects()) == 1  # 1 query, then 0 queries, as the page says


async def test_a_new_price_shows_at_once_and_drops_the_lists_of_its_category(shop: Shop) -> None:
    changes = shop.section("data_changes")
    get_product = shop.section("slow_query").get_product
    await call(changes.list_category, "coffee")

    await call(changes.change_price, await call(get_product, 1), 990)
    selects_before = len(shop.selects())
    product = await call(get_product, 1)
    listed = await call(changes.list_category, "coffee")

    assert product.price_cents == 990  # set stored it: no query
    assert [item.price_cents for item in listed if item.id == 1] == [990]
    assert len(shop.selects()) == selects_before + 1  # only the list reloads


async def test_a_rate_is_asked_once_and_an_unknown_currency_is_remembered(shop: Shop) -> None:
    get_rate = shop.section("partner").get_rate

    rates = [await call(get_rate, "EUR"), await call(get_rate, "EUR")]
    for _ in range(2):
        with pytest.raises(NotFoundError):
            await call(get_rate, "XXX")

    assert rates == [0.92, 0.92]
    assert shop.data.partner_calls == ["/rates/EUR", "/rates/XXX"]


async def test_the_report_counts_the_orders_of_the_day(shop: Shop) -> None:
    sales_report = shop.section("report").sales_report

    report = await call(sales_report, "2026-11-21")

    assert report == {"orders": 2, "revenue_cents": 3280}


async def test_a_feed_queries_only_the_prices_it_misses(shop: Shop) -> None:
    feed = shop.section("feed")

    await call(feed.main)

    assert [query.rsplit("IN ", 1)[-1] for query in shop.selects()] == ["(1, 2)", "(3)"]  # then only 3


async def test_a_token_is_kept_while_it_is_valid(shop: Shop) -> None:
    get_token = shop.section("token").get_token

    tokens = [await call(get_token), await call(get_token)]

    assert tokens[0] == tokens[1]
    assert tokens[0].access_token == "a token"


async def test_logins_quotas_and_the_nightly_job(shop: Shop) -> None:
    limits = shop.section("limits")
    for _ in range(5):
        await call(limits.failed_login, "ada@example.com")

    with pytest.raises(RateLimitedError):
        await call(limits.failed_login, "ada@example.com")  # the sixth failure: banned for an hour
    found = await call(limits.search_catalogue, "acme", "Coffee")
    await call(limits.nightly_export)

    assert [product.id for product in found] == [1]


async def test_the_product_page_is_answered_304_when_it_did_not_change(shop: Shop) -> None:
    app = shop.section("web").app
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://shop") as client:
        first = await client.get("/products/1")

        second = await client.get("/products/1", headers={"If-None-Match": first.headers["etag"]})

    assert first.status_code == 200
    assert first.json()["name"] == "Coffee beans"
    assert first.headers["cache-status"].startswith("pashe")
    assert second.status_code == 304
    assert second.content == b""
