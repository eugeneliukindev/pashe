# --8<-- [start:imports]
from dataclasses import dataclass

# --8<-- [end:imports]
from examples.shop.data_sync import payments
from examples.shop.shop_sync import cache


# --8<-- [start:show]
@dataclass
class Token:
    access_token: str
    expires_in: int  # seconds


@cache(ttl=lambda token: token.expires_in - 60, key="payments:token")
def get_token() -> Token:
    response = payments.post("/oauth/token", data={"grant_type": "client_credentials"})
    return Token(**response.json())


# --8<-- [end:show]
def main() -> None:
    # --8<-- [start:calls]
    get_token()
    # --8<-- [end:calls]
