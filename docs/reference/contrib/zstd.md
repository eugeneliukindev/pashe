# pashe.contrib.zstd

::: pashe.contrib.zstd
    options:
      members: false
      show_root_heading: false

::: pashe.contrib.zstd.ZstdCompressor
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^min_size$", "!^compress$", "!^decompress$"]  # its base tells the contract; the library calls the rest
