# Invalidation buses

::: pashe.invalidation
    options:
      members: false
      show_root_heading: false

::: pashe.invalidation.InvalidationBus

::: pashe.invalidation.AsyncInvalidationBus

::: pashe.invalidation.NoOpBus
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^publish$", "!^listen$"]  # its base tells the contract; the library calls the rest

::: pashe.invalidation.AsyncNoOpBus
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^publish$", "!^listen$"]  # its base tells the contract; the library calls the rest

::: pashe.invalidation.InvalidationHandler

::: pashe.invalidation.AsyncInvalidationHandler
