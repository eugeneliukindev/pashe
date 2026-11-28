# ASGI and WSGI

The middlewares of HTTP caching and of rate limits; they need no extra.

::: pashe.asgi
    options:
      members: false
      show_root_heading: false

::: pashe.asgi.CacheHeadersMiddleware

::: pashe.asgi.RateLimitMiddleware
::: pashe.wsgi
    options:
      members: false
      show_root_heading: false

::: pashe.wsgi.CacheHeadersMiddleware
