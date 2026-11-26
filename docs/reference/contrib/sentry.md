# pashe.contrib.sentry

::: pashe.contrib.sentry
    options:
      members: false
      show_root_heading: false

::: pashe.contrib.sentry.SentryHook
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^on_error$", "!^on_circuit$"]  # its base tells the contract; the library calls the rest
