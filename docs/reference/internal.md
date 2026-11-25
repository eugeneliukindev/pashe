# Internal API

What is documented here is not public: it can change in any release. Do not import it; it is
here so that the types in the signatures of the public API lead somewhere, for people and for
LLMs reading the code.

## Decorators

What the decorator methods of a cache return. Apply them; do not make them by hand.

::: pashe._internal.sync.cache.cached.CachedFunctionDecorator
    options:
      merge_init_into_class: false

::: pashe._internal.async_.cache.cached.AsyncCachedFunctionDecorator
    options:
      merge_init_into_class: false

::: pashe._internal.sync.cache.cached.CachedValueDecorator
    options:
      merge_init_into_class: false

::: pashe._internal.async_.cache.cached.AsyncCachedValueDecorator
    options:
      merge_init_into_class: false

::: pashe._internal.sync.cache.cached_batch.CachedBatchFunctionDecorator
    options:
      merge_init_into_class: false

::: pashe._internal.async_.cache.cached_batch.AsyncCachedBatchFunctionDecorator
    options:
      merge_init_into_class: false

::: pashe._internal.sync.cache.around.LockedDecorator
    options:
      merge_init_into_class: false

::: pashe._internal.async_.cache.around.AsyncLockedDecorator
    options:
      merge_init_into_class: false

::: pashe._internal.sync.cache.around.RateLimitedDecorator
    options:
      merge_init_into_class: false

::: pashe._internal.async_.cache.around.AsyncRateLimitedDecorator
    options:
      merge_init_into_class: false

::: pashe._internal.sync.cache.around.InvalidatingDecorator
    options:
      merge_init_into_class: false

::: pashe._internal.async_.cache.around.AsyncInvalidatingDecorator
    options:
      merge_init_into_class: false

## Types

::: pashe._internal.web.headers.Directive
