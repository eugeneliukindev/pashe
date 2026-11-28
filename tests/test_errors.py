"""The errors of pashe: what they say, and that they cross processes as they are."""

from __future__ import annotations

import pickle

import pytest

from pashe.errors import (
    CircuitOpenError,
    LockLostError,
    LockTimeoutError,
    NotFoundError,
    OverloadedError,
    PasheError,
    RateLimitedError,
    ValueTooLargeError,
)


@pytest.mark.parametrize(
    "error",
    [
        NotFoundError("user:1"),
        LockLostError("report", expired=True),
        LockTimeoutError("report", 5.0),
        CircuitOpenError(3),
        OverloadedError(),
        ValueTooLargeError(2048, 1024),
        RateLimitedError(1.5),
    ],
    ids=lambda error: type(error).__name__,
)
def test_an_error_keeps_its_fields_and_its_message_through_pickle(error: PasheError) -> None:
    copied = pickle.loads(pickle.dumps(error))  # noqa: S301 - our own bytes

    assert type(copied) is type(error)
    assert vars(copied) == vars(error)
    assert str(copied) == str(error)
