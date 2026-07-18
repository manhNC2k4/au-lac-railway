# -*- coding: utf-8 -*-
"""Clock injection — demo cần tick thời gian giả để chứng minh expiry.
Không rải rác datetime.now() trong code; mọi nơi cần "bây giờ" gọi qua đây."""
from datetime import datetime, timezone


class Clock:
    """Clock thật — dùng cho production/dev thường."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FixedClock(Clock):
    """Clock demo/test — set/advance thủ công để test expiry mà không cần sleep()."""

    def __init__(self, start: datetime):
        self._now = start

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float) -> None:
        from datetime import timedelta
        self._now = self._now + timedelta(seconds=seconds)

    def set(self, when: datetime) -> None:
        self._now = when
