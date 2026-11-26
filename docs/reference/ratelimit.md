# pashe.ratelimit

::: pashe.ratelimit
    options:
      members: false
      show_root_heading: false

::: pashe.ratelimit.SlidingWindow

::: pashe.ratelimit.FixedWindow
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^ban_seconds$"]  # the library calls it, not you

::: pashe.ratelimit.Limit

::: pashe.ratelimit.per_second

::: pashe.ratelimit.per_minute

::: pashe.ratelimit.per_hour

::: pashe.ratelimit.RateLimitState
