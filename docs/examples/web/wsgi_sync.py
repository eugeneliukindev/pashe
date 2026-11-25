# --8<-- [start:show]
from collections.abc import Iterable
from wsgiref.types import StartResponse, WSGIEnvironment

from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.hooks import CacheHeadersHook
from pashe.wsgi import CacheHeadersMiddleware

headers = CacheHeadersHook()  # records the cached calls of each request
cache = Cache(MemoryBackend(), hooks=[headers])  # every cache the application calls gets it


@cache(ttl=60, key="product:{product_id}")
def get_product(product_id: int) -> str:
    return f'{{"id": {product_id}, "name": "Kettle"}}'  # your query to the database


def app(_environ: WSGIEnvironment, start_response: StartResponse) -> Iterable[bytes]:  # Django, Flask
    body = get_product(1).encode()
    start_response("200 OK", [("Content-Type", "application/json"), ("Content-Length", str(len(body)))])
    return [body]


application = CacheHeadersMiddleware(app, hook=headers)


# --8<-- [end:show]
