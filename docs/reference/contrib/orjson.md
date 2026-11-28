# pashe.contrib.orjson

::: pashe.contrib.orjson
    options:
      members: false
      show_root_heading: false

::: pashe.contrib.orjson.OrjsonCodec
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^encode$", "!^check$", "!^decode$"]  # its base tells the contract; the library calls the rest
