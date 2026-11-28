# pashe.codecs

::: pashe.codecs
    options:
      members: false
      show_root_heading: false

::: pashe.codecs.Codec

::: pashe.codecs.JsonCodec
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^encode$", "!^validate$", "!^decode$"]  # its base tells the contract; the library calls the rest

::: pashe.codecs.PickleCodec
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^encode$", "!^decode$"]  # its base tells the contract; the library calls the rest
