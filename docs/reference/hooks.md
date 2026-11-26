# Hooks

::: pashe.hooks
    options:
      members: false
      show_root_heading: false

::: pashe.hooks.Hook

::: pashe.hooks.LoggingHook

::: pashe.hooks.CacheHeadersHook
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^recording$"]  # the library calls it, not you

::: pashe.hooks.Outcome

::: pashe.hooks.CacheStatus

::: pashe.hooks.Failure

::: pashe.hooks.Operation

::: pashe.hooks.RateLimitDecision

::: pashe.hooks.NearRead

::: pashe.hooks.Circuit
