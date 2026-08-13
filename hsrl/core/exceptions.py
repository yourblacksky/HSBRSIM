"""Typed engine failures that callers can handle without parsing strings."""

from __future__ import annotations


class CombatResolutionTimeout(TimeoutError):
    """A deterministic combat-resolution budget was exhausted.

    This is intentionally driven by engine work units instead of wall-clock
    time so identical seeds fail at the same boundary on every machine.
    """

    def __init__(
        self,
        *,
        budget: str,
        limit: int,
        observed: int,
        turn: int,
        player_ids: tuple[int | None, int | None],
    ) -> None:
        self.budget = budget
        self.limit = int(limit)
        self.observed = int(observed)
        self.turn = int(turn)
        self.player_ids = player_ids
        super().__init__(
            f"combat {budget} budget exhausted on turn {turn}: "
            f"observed={observed}, limit={limit}, players={player_ids}"
        )
