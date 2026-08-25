"""Starter controllers for the build-your-own-controller notebook."""

from __future__ import annotations

import random
from collections import defaultdict
from typing import TYPE_CHECKING

from blueberries_voi.controller.session_loop import ControllerContext  # noqa: TC001
from blueberries_voi.sim.case_round import case_round

if TYPE_CHECKING:
    from blueberries_voi.controller.session_loop import ControllerStepLog

TARGET_UNITS: int = 48


def weekday_index(episode_day: int) -> int:
    """Calendar weekday index 0=Monday … 6=Sunday for ``episode_day``."""
    return int(episode_day % 7)


def discretize_on_hand(
    on_hand: int,
    *,
    max_on_hand: int = 80,
    n_bins: int = 10,
) -> int:
    """Bin total on-hand into ``[0, n_bins - 1]`` for tabular RL."""
    if max_on_hand <= 0:
        msg = f"max_on_hand must be positive, got {max_on_hand}"
        raise ValueError(msg)
    if n_bins <= 0:
        msg = f"n_bins must be positive, got {n_bins}"
        raise ValueError(msg)
    clamped = max(0, min(int(on_hand), max_on_hand))
    if clamped == max_on_hand:
        return n_bins - 1
    return int(clamped * n_bins // max_on_hand)


class ControllerTemplate:
    """Base class for notebook starter controllers."""

    def order(self, ctx: ControllerContext) -> int:
        raise NotImplementedError


class NaiveBaseStockController(ControllerTemplate):
    """Top-up to ``target_units`` with case rounding on non-order days returns 0."""

    def __init__(
        self,
        *,
        target_units: int = TARGET_UNITS,
        case_size: int = 8,
    ) -> None:
        self.target_units = int(target_units)
        self.case_size = int(case_size)

    def order(self, ctx: ControllerContext) -> int:
        if not ctx.can_order:
            return 0
        pipeline_units = sum(int(q) for q in ctx.pending_orders.values())
        gap = max(0.0, float(self.target_units - ctx.on_hand - pipeline_units))
        return case_round(gap, self.case_size)


class TabularQLearningController(ControllerTemplate):
    """ε-greedy tabular Q-learning on (weekday, on_hand_bin) → discrete order units."""

    def __init__(
        self,
        actions: list[int],
        *,
        epsilon: float = 0.15,
        learning_rate: float = 0.1,
        discount: float = 0.0,
        max_on_hand: int = 80,
        on_hand_bins: int = 10,
        seed: int = 0,
    ) -> None:
        self.actions = [int(a) for a in actions]
        if not self.actions:
            msg = "actions must be non-empty"
            raise ValueError(msg)
        self.epsilon = float(epsilon)
        self.learning_rate = float(learning_rate)
        self.discount = float(discount)
        self.max_on_hand = int(max_on_hand)
        self.on_hand_bins = int(on_hand_bins)
        self._rng = random.Random(seed)
        self._q: dict[tuple[int, int], dict[int, float]] = defaultdict(
            lambda: defaultdict(float)
        )
        self._last_state: tuple[int, int] | None = None
        self._last_action: int | None = None

    def _state(self, ctx: ControllerContext) -> tuple[int, int]:
        wd = weekday_index(ctx.episode_day)
        bin_idx = discretize_on_hand(
            ctx.on_hand,
            max_on_hand=self.max_on_hand,
            n_bins=self.on_hand_bins,
        )
        return wd, bin_idx

    def order(self, ctx: ControllerContext) -> int:
        if not ctx.can_order:
            self._last_state = None
            self._last_action = None
            return 0
        state = self._state(ctx)
        if self._rng.random() < self.epsilon:
            action = self._rng.choice(self.actions)
        else:
            q_row = self._q[state]
            action = max(self.actions, key=lambda a: q_row.get(a, 0.0))
        self._last_state = state
        self._last_action = action
        return int(action)

    def observe(self, ctx: ControllerContext, log: ControllerStepLog) -> None:
        if self._last_state is None or self._last_action is None:
            return
        reward = float(log.day_profit)
        state = self._last_state
        action = self._last_action
        next_state = self._state(ctx)
        q_row = self._q[state]
        best_next = max(
            (self._q[next_state].get(a, 0.0) for a in self.actions),
            default=0.0,
        )
        old = q_row.get(action, 0.0)
        target = reward + self.discount * best_next
        q_row[action] = old + self.learning_rate * (target - old)
        self._last_state = None
        self._last_action = None


__all__ = [
    "TARGET_UNITS",
    "ControllerTemplate",
    "NaiveBaseStockController",
    "TabularQLearningController",
    "discretize_on_hand",
    "weekday_index",
]
