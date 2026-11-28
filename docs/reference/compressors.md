# pashe.compressors

::: pashe.compressors
    options:
      members: false
      show_root_heading: false

::: pashe.compressors.Compressor

::: pashe.compressors.GzipCompressor
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^min_size$", "!^compress$", "!^decompress$"]  # its base tells the contract; the library calls the rest

::: pashe.compressors.NoOpCompressor
    options:
      filters: ["!^_[^_]", "!^__(?!(call|enter|exit|aenter|aexit)__$)", "!^compress$", "!^decompress$"]  # its base tells the contract; the library calls the rest
