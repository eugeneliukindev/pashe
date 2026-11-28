# --8<-- [start:imports]
from dataclasses import dataclass

# --8<-- [end:imports]
from examples.shop.data_async import payments, start
from examples.shop.shop_async import cache


# --8<-- [start:show]
@dataclass
class Token:
    access_token: str
    expires_in: int  # seconds


@cache(ttl=lambda token: token.expires_in - 60, key="payments:token")
async def get_token() -> Token:
    response = await payments.post("/oauth/token", data={"grant_type": "client_credentials"})
    return Token(**response.json())


# --8<-- [end:show]
async def main() -> None:
    await start()  # opens the database of the shop
    # --8<-- [start:calls]
    await get_token()
    # --8<-- [end:calls]
