# pashe.contrib.prometheus

::: pashe.contrib.prometheus
    options:
      members: false
      show_root_heading: false

::: pashe.contrib.prometheus.PrometheusMetricsHook
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^on_call$", "!^on_error$", "!^on_rate_limit$", "!^on_near_read$", "!^on_near_flush$", "!^on_circuit$"]  # its base tells the contract; the library calls the rest
