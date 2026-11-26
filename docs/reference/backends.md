# Backends

::: pashe.backends
    options:
      members: false
      show_root_heading: false

::: pashe.backends.Backend

::: pashe.backends.AsyncBackend

::: pashe.backends.MemoryBackend
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^get$", "!^get_many$", "!^set$", "!^set_many$", "!^set_if_absent$", "!^delete$", "!^incr$", "!^expire$", "!^ttl$", "!^delete_if_equals$", "!^expire_if_equals$", "!^ping$", "!^close$", "!^clear$", "!^delete_many$"]  # its base tells the contract; the library calls the rest

::: pashe.backends.AsyncMemoryBackend
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^get$", "!^get_many$", "!^set$", "!^set_many$", "!^set_if_absent$", "!^delete$", "!^incr$", "!^expire$", "!^ttl$", "!^delete_if_equals$", "!^expire_if_equals$", "!^ping$", "!^aclose$", "!^clear$", "!^delete_many$"]  # its base tells the contract; the library calls the rest

::: pashe.backends.SQLiteBackend
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^get_many$", "!^set_many$", "!^set_if_absent$", "!^delete$", "!^incr$", "!^expire$", "!^ttl$", "!^delete_if_equals$", "!^expire_if_equals$", "!^ping$", "!^close$"]  # its base tells the contract; the library calls the rest

::: pashe.backends.AsyncSQLiteBackend
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^get_many$", "!^set_many$", "!^set_if_absent$", "!^delete$", "!^incr$", "!^expire$", "!^ttl$", "!^delete_if_equals$", "!^expire_if_equals$", "!^ping$", "!^aclose$"]  # its base tells the contract; the library calls the rest

::: pashe.backends.NearCacheBackend
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^get$", "!^get_many$", "!^set$", "!^set_many$", "!^set_if_absent$", "!^delete$", "!^incr$", "!^expire$", "!^ttl$", "!^delete_if_equals$", "!^expire_if_equals$", "!^ping$", "!^close$"]  # its base tells the contract; the library calls the rest

::: pashe.backends.AsyncNearCacheBackend
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^get$", "!^get_many$", "!^set$", "!^set_many$", "!^set_if_absent$", "!^delete$", "!^incr$", "!^expire$", "!^ttl$", "!^delete_if_equals$", "!^expire_if_equals$", "!^ping$", "!^aclose$"]  # its base tells the contract; the library calls the rest

::: pashe.backends.Breaker
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^guarding$"]  # the library calls it, not you

::: pashe.backends.CircuitBreaker
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^before_call$", "!^on_success$", "!^on_cancel$", "!^on_failure$", "!^guarding$"]  # its base tells the contract; the library calls the rest

::: pashe.backends.NoOpBreaker
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^before_call$", "!^on_success$", "!^on_failure$", "!^on_cancel$", "!^guarding$"]  # its base tells the contract; the library calls the rest
