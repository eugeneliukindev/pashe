# --8<-- [start:imports]
import httpx

from pashe.options import Negative, Stale

# --8<-- [end:imports]
from examples.shop.data_sync import partner
from examples.shop.shop_sync import cache


# --8<-- [start:show]
class UnknownCurrencyError(LookupError):
    pass


@cache(
    ttl=600,
    stale=Stale(if_error=3_600, if_error_on=(httpx.HTTPError,)),
    negative=Negative(on=(UnknownCurrencyError,), ttl=600),
)
def get_rate(currency: str) -> float:
    response = partner.get(f"/rates/{currency}")
    if response.status_code == httpx.codes.NOT_FOUND:
        raise UnknownCurrencyError(currency)
    response.raise_for_status()
    return float(response.json()["rate"])


# --8<-- [end:show]
def main() -> None:
    # --8<-- [start:calls]
    get_rate("EUR")
    # --8<-- [end:calls]
