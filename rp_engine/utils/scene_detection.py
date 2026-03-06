"""Scene detection utility — groups exchange numbers into scene clusters."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Scene:
    """A cluster of consecutive exchanges forming a narrative scene."""
    exchanges: list[int] = field(default_factory=list)

    @property
    def start(self) -> int:
        return self.exchanges[0] if self.exchanges else 0

    @property
    def end(self) -> int:
        return self.exchanges[-1] if self.exchanges else 0

    @property
    def size(self) -> int:
        return len(self.exchanges)


def group_into_scenes(
    exchange_numbers: list[int],
    gap_threshold: int = 3,
) -> list[Scene]:
    """Group exchange numbers into scene clusters.

    A gap of more than ``gap_threshold`` exchanges between consecutive
    numbers indicates a scene break.

    Args:
        exchange_numbers: Unsorted list of exchange numbers.
        gap_threshold: Maximum gap between exchanges in the same scene.

    Returns:
        List of Scene objects, ordered by start exchange number.
    """
    if not exchange_numbers:
        return []

    sorted_nums = sorted(set(exchange_numbers))
    scenes: list[Scene] = []
    current = Scene(exchanges=[sorted_nums[0]])

    for i in range(1, len(sorted_nums)):
        if sorted_nums[i] - sorted_nums[i - 1] > gap_threshold:
            scenes.append(current)
            current = Scene(exchanges=[sorted_nums[i]])
        else:
            current.exchanges.append(sorted_nums[i])

    scenes.append(current)
    return scenes
