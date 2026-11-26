# pashe.contrib.redis

::: pashe.contrib.redis
    options:
      members: false
      show_root_heading: false

::: pashe.contrib.redis.RedisBackend
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^get$", "!^get_many$", "!^set$", "!^set_many$", "!^set_if_absent$", "!^delete$", "!^incr$", "!^expire$", "!^ttl$", "!^delete_if_equals$", "!^expire_if_equals$", "!^ping$", "!^close$"]  # its base tells the contract; the library calls the rest

::: pashe.contrib.redis.AsyncRedisBackend
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^get$", "!^get_many$", "!^set$", "!^set_many$", "!^set_if_absent$", "!^delete$", "!^incr$", "!^expire$", "!^ttl$", "!^delete_if_equals$", "!^expire_if_equals$", "!^ping$", "!^aclose$"]  # its base tells the contract; the library calls the rest

::: pashe.contrib.redis.RedisPubSubBus
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^publish$", "!^listen$"]  # its base tells the contract; the library calls the rest

::: pashe.contrib.redis.AsyncRedisPubSubBus
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^publish$", "!^listen$"]  # its base tells the contract; the library calls the rest

::: pashe.contrib.redis.RedisTrackingBus
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^publish$", "!^listen$"]  # its base tells the contract; the library calls the rest

::: pashe.contrib.redis.AsyncRedisTrackingBus
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^publish$", "!^listen$"]  # its base tells the contract; the library calls the rest
