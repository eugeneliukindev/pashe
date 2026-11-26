"""The reference tells every field of every group of options: it is made of their docstrings."""

from __future__ import annotations

import dataclasses
import inspect
import re

import pytest

from pashe.options import Fallback, IfError, IfSlow, Negative, Stale, Stampede, Store
from pashe.ratelimit import FixedWindow, RateLimitState, SlidingWindow

_GROUPS = (Stale, IfError, IfSlow, Stampede, Negative, Store, Fallback, SlidingWindow, FixedWindow, RateLimitState)


@pytest.mark.parametrize("group", _GROUPS, ids=lambda group: group.__name__)
def test_the_docstring_of_a_group_tells_every_field(group: type) -> None:
    attributes = (inspect.getdoc(group) or "").partition("Attributes:")[2].partition("\n\n")[0]

    told = set(re.findall(r"^    (\w+):", attributes, re.MULTILINE))

    assert told == {field.name for field in dataclasses.fields(group)}
