# pashe.contrib.opentelemetry

::: pashe.contrib.opentelemetry
    options:
      members: false
      show_root_heading: false

::: pashe.contrib.opentelemetry.OtelMetricsHook
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^on_call$", "!^on_error$", "!^on_rate_limit$", "!^on_near_read$", "!^on_near_flush$", "!^on_circuit$"]  # its base tells the contract; the library calls the rest

::: pashe.contrib.opentelemetry.OtelSpanEventsHook
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^on_call$", "!^on_error$"]  # its base tells the contract; the library calls the rest
