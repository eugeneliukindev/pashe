# Hooks

::: pashe.hooks
    options:
      members: false
      show_root_heading: false

::: pashe.hooks.Hook

::: pashe.hooks.LoggingHook
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^on_error$", "!^on_circuit$"]  # its base tells the contract; the library calls the rest

::: pashe.hooks.CacheHeadersHook
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^on_call$", "!^recording$"]  # its base tells the contract; the library calls the rest

::: pashe.hooks.Outcome

::: pashe.hooks.CacheStatus

::: pashe.hooks.Failure

::: pashe.hooks.Operation

::: pashe.hooks.RateLimitDecision

::: pashe.hooks.NearRead

::: pashe.hooks.Circuit
