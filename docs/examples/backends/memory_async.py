from pashe.backends import AsyncMemoryBackend

backend = AsyncMemoryBackend(max_entries=10_000, max_bytes=64 * 1024 * 1024)
