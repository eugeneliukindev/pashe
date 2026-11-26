# Backends

::: pashe.backends
    options:
      members: false
      show_root_heading: false

::: pashe.backends.Backend

::: pashe.backends.AsyncBackend

::: pashe.backends.MemoryBackend
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^clear$", "!^delete_many$"]  # the library calls it, not you

::: pashe.backends.AsyncMemoryBackend
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^clear$", "!^delete_many$"]  # the library calls it, not you

::: pashe.backends.SQLiteBackend

::: pashe.backends.AsyncSQLiteBackend

::: pashe.backends.NearCacheBackend

::: pashe.backends.AsyncNearCacheBackend

::: pashe.backends.Breaker
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^guarding$"]  # the library calls it, not you

::: pashe.backends.CircuitBreaker
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^guarding$"]  # the library calls it, not you

::: pashe.backends.NoOpBreaker
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^guarding$"]  # the library calls it, not you
