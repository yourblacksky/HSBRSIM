"""Game lifecycle management — create game, auto-play opponents, run turns.

Handles:
  - Creating a Game with 8 heroes (player 0 = human)
  - Auto-playing opponents (1-7) with SearchAgent heuristic
  - Turn setup (gold, refresh, trinket offers)
  - Combat resolution
"""
from __future__ import annotations

import random
from typing import Optional

import hsrl.cards.heroes.pool  # noqa — register heroes
import hsrl.cards.heroes.scripts  # noqa
import hsrl.cards.minions.pool  # noqa — register minions
import hsrl.cards.minions.scripts  # noqa
import hsrl.cards.minions.tokens  # noqa
import hsrl.cards.spells  # noqa
import hsrl.cards.trinkets.scripts  # noqa
import hsrl.cards.rewards.scripts  # noqa
import hsrl.cards.anomalies.scripts  # noqa

from hsrl.agents.agent_utils import simulate_action, populate_tavern
from hsrl.core.card_db import CARDS
from hsrl.core.enums import CardType, GameTag
from hsrl.core.game import Game
from hsrl.env.action import (
    END_TURN,
    REFRESH,
    UPGRADE,
    BUY_OFFSET,
    SELL_OFFSET,
    build_action_mask,
    decode_action,
)

HERO_IDS = [
    "BG20_HERO_100",  # Rokara
    "BG20_HERO_101",  # Xyrella
    "BG20_HERO_102",  # Overlord Saurfang
    "BG20_HERO_103",  # Death Speaker Blackthorn
    "BG20_HERO_201",  # Vol'jin
    "BG20_HERO_202",  # Master Nguyen
    "BG20_HERO_242",  # Guff Runetotem
    "BG20_HERO_280",  # Kurtrus Ashfallen
]


class GameRunner:
    """Manages a single Battlegrounds game with one human player."""

    def __init__(self, seed: int = 42, max_turns: int = 15):
        self.seed = seed
        self.max_turns = max_turns
        self.rng = random.Random(seed)
        self.game: Optional[Game] = None

    def create_game(self) -> tuple[Game, int]:
        """Create a new game. Returns (game, player_index)."""
        hero_count = 8
        heroes = HERO_IDS[:hero_count]
        self.game = Game.create_game(heroes, CARDS, seed=self.seed, apply_anomaly=True)

        # Player 0 is the human
        human_idx = 0
        return self.game, human_idx

    def auto_play_opponents(self):
        """Auto-play all non-human players (1-7) with greedy Q-score heuristic."""
        game = self.game
        for idx in range(1, 8):
            player = game.players[idx]
            if not player.is_alive:
                continue

            action_count = 0
            while action_count < 50:
                mask = build_action_mask(game, player)
                legal = [a for a in range(50) if mask[a]]
                if not legal:
                    break

                action = self._greedy_action(game, player, mask, legal)
                if action == END_TURN:
                    break

                simulate_action(player, action)
                if action == REFRESH:
                    populate_tavern(player, game.rng)
                    self._auto_play_hand(player)
                action_count += 1

            self._auto_play_hand(player)
            simulate_action(player, END_TURN)

    @staticmethod
    def _greedy_action(game, player, mask, legal):
        board_count = len([m for m in player.board if not m.dead])
        buy_actions = [a for a in legal if BUY_OFFSET <= a < BUY_OFFSET + 7]
        sell_actions = [a for a in legal if SELL_OFFSET <= a < SELL_OFFSET + 7]

        # Auto-play minions
        for a in legal:
            if 14 <= a < 24:  # PLAY_OFFSET range
                slot = a - 14
                if slot < len(player.hand):
                    card = player.hand[slot]
                    if card.get_tag(GameTag.CARDTYPE, 0) == CardType.MINION:
                        return a

        # Buy best minion when board not full
        if board_count < 7 and buy_actions and player.gold >= 3:
            best_buy, best_score = None, -1
            for a in buy_actions:
                slot = a - BUY_OFFSET
                if slot < len(player.tavern):
                    e = player.tavern[slot]
                    if e.get_tag(GameTag.CARDTYPE, 0) == CardType.MINION:
                        s = e.atk + e.health
                        if s > best_score:
                            best_score = s
                            best_buy = a
            if best_buy is not None:
                return best_buy

        # Upgrade on curve
        expected = {1:1, 2:1, 3:2, 4:2, 5:3, 6:3, 7:4, 8:4, 9:5, 10:5, 11:6,
                    12:6, 13:6, 14:6, 15:6}.get(game.turn, player.tavern_tier)
        if player.tavern_tier < expected and UPGRADE in legal:
            return UPGRADE

        # Sell weak + buy strong
        if board_count >= 7 and buy_actions and sell_actions:
            living = [m for m in player.board if not m.dead]
            weakest = min(range(len(living)),
                          key=lambda i: living[i].atk + living[i].health)
            best_buy_score = -1
            for a in buy_actions:
                slot = a - BUY_OFFSET
                if slot < len(player.tavern):
                    e = player.tavern[slot]
                    if e.get_tag(GameTag.CARDTYPE, 0) == CardType.MINION:
                        s = e.atk + e.health
                        if s > best_buy_score:
                            best_buy_score = s
            if best_buy_score > (living[weakest].atk + living[weakest].health):
                return SELL_OFFSET + weakest

        # Smart refresh
        if REFRESH in legal:
            free = player.get_tag(GameTag.FREE_REFRESH_REMAINING, 0)
            min_cost = min(
                (e.get_tag(GameTag.COST, 3) for e in player.tavern
                 if e.get_tag(GameTag.CARDTYPE, 0) in (CardType.MINION, 42)),
                default=99)
            if free > 0 or (player.gold >= 1 + min_cost and board_count < 7):
                return REFRESH

        # Fallback: random safe action
        safe = [a for a in legal if not (SELL_OFFSET <= a < SELL_OFFSET + 7) and a != END_TURN]
        return random.choice(safe) if safe else END_TURN

    def start_turn(self):
        """Prepare the turn: set gold, refresh tavern, handle trinkets."""
        game = self.game
        turn = game.turn

        for p in game.players:
            if not p.is_alive:
                continue
            # Gold = min(3 + turn - 1, 10)
            p.set_tag(GameTag.GOLD, int(min(3 + turn - 1, 10)))
            p.set_tag(GameTag.HERO_POWER_USED, False)
            p.set_tag(GameTag.SECONDARY_HERO_POWER_USED, False)
            # Reduce upgrade cost
            cost = p.get_tag(GameTag.TAVERN_UPGRADE_COST, 0)
            if cost > 0:
                p.set_tag(GameTag.TAVERN_UPGRADE_COST, cost - 1)

        # Refresh all taverns and auto-play hand minions
        for p in game.players:
            if not p.is_alive:
                continue
            game.refresh_tavern(p)
            self._auto_play_hand(p)

        # Handle trinket offers (turn 6 = lesser, turn 9 = greater)
        if turn in (6, 9):
            game._offer_trinkets(game.players[0])

    def run_combat(self):
        """Run combat phase for this turn."""
        game = self.game
        # Pair up alive players for combat
        alive = [p for p in game.players if p.is_alive]
        if len(alive) < 2:
            return

        # Simple pairing: adjacent pairs
        random.shuffle(alive)
        for i in range(0, len(alive) - 1, 2):
            attacker = alive[i]
            defender = alive[i + 1]
            game._run_combat(attacker, defender)

    def human_end_turn(self, player_idx: int = 0):
        game = self.game
        player = game.players[player_idx]
        self._auto_play_hand(player)
        simulate_action(player, END_TURN)

    @staticmethod
    def _auto_play_hand(p):
        """Auto-play all minions from hand onto board."""
        board_count = len([m for m in p.board if not m.dead])
        for card in list(p.hand):
            if board_count >= 7:
                break
            ct = card.get_tag(GameTag.CARDTYPE, 0)
            if ct == CardType.MINION:
                p.hand.remove(card)
                p.board.append(card)
                board_count += 1
