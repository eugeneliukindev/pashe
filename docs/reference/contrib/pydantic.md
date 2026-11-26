# pashe.contrib.pydantic

::: pashe.contrib.pydantic
    options:
      members: false
      show_root_heading: false

::: pashe.contrib.pydantic.PydanticCodec
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^check$", "!^encode$", "!^decode$"]  # its base tells the contract; the library calls the rest
