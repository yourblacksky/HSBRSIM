"""
Convert HDT game state messages into Trajectory objects for opponent replay.

Takes per-turn HDT game state data (collected via the advisor server) and
produces Trajectory objects compatible with the trajectory opponent system.
Each turn's LAST game_state message (end of recruit phase) becomes a
TurnSnapshot with board, health, armor, tier, and trinkets.

Usage:
    python -m hsrl.advisor.trajectory_converter --input data/real_games/20260505/ \\
        --output data/trajectories/
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Optional

from hsrl.trajectory.record import MinionSnapshot, TurnSnapshot, Trajectory

# Ensure card database is populated before parsing any game files
import hsrl.cards.minions.pool as _mp  # noqa
import hsrl.cards.minions.scripts as _ms  # noqa
import hsrl.cards.minions.tokens as _mt  # noqa
import hsrl.cards.heroes.pool as _hp  # noqa
import hsrl.cards.heroes.scripts as _hs  # noqa
import hsrl.cards.trinkets.scripts as _ts  # noqa
import hsrl.cards.rewards.scripts as _rs  # noqa
import hsrl.cards.anomalies.scripts as _as  # noqa


def parse_hdt_game_file(filepath: str) -> Optional[Trajectory]:
    """Parse a single HDT game JSONL file into a Trajectory.

    The file contains one JSON object per line: game_start, game_state (×N),
    game_end. We extract the last game_state per turn to get end-of-recruit
    board snapshots.
    """
    with open(filepath) as f:
        lines = [line.strip() for line in f if line.strip()]

    if not lines:
        return None

    game_id = None
    hero_id = ""
    hero_name = ""
    turns = {}  # turn_number → last game_state for that turn
    final_placement = 0
    game_end_data = None

    for line in lines:
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        msg_type = msg.get("type", "")

        if msg_type == "game_start":
            game_id = msg.get("game_id", os.path.basename(filepath))
            hero_id = msg.get("hero_card_id", "")
            hero_name = msg.get("hero_name", "")

        elif msg_type in ("game_state", "step"):
            # "step" format: state is nested; "game_state" is flat
            state = msg.get("state", msg) if msg_type == "step" else msg
            turn = state.get("turn", msg.get("turn", 0))
            if turn > 0:
                # Also extract hero from player state
                p = state.get("player", {})
                h = p.get("hero_card_id", "")
                if h and not hero_id:
                    hero_id = h
                turns[turn] = state

        elif msg_type == "game_end":
            game_end_data = msg
            final_placement = msg.get("placement", 0)

    if not game_id or not turns:
        return None

    # Build TurnSnapshots from the last game_state per turn
    turn_snapshots = []
    for turn_num in sorted(turns.keys()):
        msg = turns[turn_num]
        player = msg.get("player", {})
        # Use "board" field (C# plugin v2.3+ correctly separates board/tavern).
        # Fall back to "tavern" for old data affected by the pre-2.3 bug where
        # board minions leaked into the tavern field.
        board_data = msg.get("board", [])
        if not board_data:
            board_data = msg.get("tavern", [])
        trinkets_data = msg.get("trinkets", [])

        # Convert board slots to MinionSnapshots
        board = []
        for slot in board_data:
            if not slot:
                continue
            # slot is a dict from HDT; extract fields
            card_id = slot.get("card_id", "")
            if not card_id:
                continue  # Skip slots without card_id (old data)

            # HDT reports golden cards as "XXX_G" — strip suffix, set flag
            is_golden = slot.get("golden", False) or card_id.endswith("_G")
            if card_id.endswith("_Gt"):
                card_id = card_id[:-3] + "t"  # BG34_731_Gt → BG34_731t
                is_golden = True
            elif card_id.endswith("_G"):
                card_id = card_id[:-2]  # BG31_035_G → BG31_035
                is_golden = True

            # Skip if card_id not in CARDS (blood gems, spells, tokens)
            from hsrl.core.card_db import CARDS
            if CARDS.get(card_id) is None:
                continue

            ms = MinionSnapshot(
                card_id=card_id,
                is_golden=is_golden,
                atk=slot.get("atk", 0),
                health=slot.get("health", 0),
                max_health=slot.get("max_health", 0),
                race=_parse_race(slot.get("race", "")),
                taunt=slot.get("taunt", False),
                divine_shield=slot.get("divine_shield", False),
                poisonous=slot.get("poisonous", False),
                venomous=slot.get("venomous", False),
                reborn=slot.get("reborn", False),
                windfury=slot.get("windfury", False),
                cleave=slot.get("cleave", False),
                position=0,  # Position is implicit from list order
            )
            board.append(ms)

        # Extract trinket card_ids
        trinket_ids = []
        for t in trinkets_data:
            if t and t.get("card_id"):
                trinket_ids.append(t["card_id"])

        ts = TurnSnapshot(
            turn=turn_num,
            health=player.get("health", 30),
            armor=player.get("armor", 0),
            tavern_tier=player.get("tavern_tier", 1),
            gold=player.get("gold", 0),
            board=board,
            trinkets=trinket_ids,
            hero_power_used=player.get("hero_power_used", False),
        )
        turn_snapshots.append(ts)

    if not turn_snapshots:
        return None

    last_turn = turn_snapshots[-1]
    return Trajectory(
        game_id=game_id,
        hero_id=hero_id,
        hero_name=hero_name,
        seed=0,
        active_tribes=[],  # Not captured by HDT
        placement=final_placement,
        final_health=last_turn.health,
        final_tier=last_turn.tavern_tier,
        turns=turn_snapshots,
        anomaly_id="",
    )


def _parse_race(race_str: str) -> int:
    """Convert HDT race string to Race enum int."""
    from hsrl.core.enums import Race
    mapping = {
        "INVALID": Race.INVALID, "BEAST": Race.BEAST, "DEMON": Race.DEMON,
        "DRAGON": Race.DRAGON, "ELEMENTAL": Race.ELEMENTAL,
        "MECH": Race.MECH, "MECHANICAL": Race.MECH,
        "MURLOC": Race.MURLOC, "NAGA": Race.NAGA,
        "PIRATE": Race.PIRATE, "QUILBOAR": Race.QUILBOAR,
        "UNDEAD": Race.UNDEAD, "ALL": Race.ALL,
    }
    return mapping.get(race_str.upper(), Race.INVALID).value


def convert_directory(input_dir: str, output_dir: str) -> int:
    """Convert all HDT game files in a directory to trajectory JSON files."""
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    count = 0
    for f in sorted(input_path.iterdir()):
        if f.suffix not in (".jsonl", ".json"):
            continue
        traj = parse_hdt_game_file(str(f))
        if traj is None:
            continue

        out_file = output_path / f"{traj.game_id}.json"
        with open(out_file, "w") as fout:
            json.dump(traj.to_dict(), fout, indent=2)

        # Update index
        index_file = output_path / "index.jsonl"
        with open(index_file, "a") as idx:
            idx.write(json.dumps({
                "game_id": traj.game_id,
                "hero_id": traj.hero_id,
                "hero_name": traj.hero_name,
                "active_tribes": traj.active_tribes,
                "placement": traj.placement,
                "anomaly_id": traj.anomaly_id,
            }) + "\n")

        count += 1

    return count


def main():
    parser = argparse.ArgumentParser(
        description="Convert HDT game state data to Trajectory format")
    parser.add_argument("--input", type=str, required=True,
                        help="Directory containing HDT game JSONL files")
    parser.add_argument("--output", type=str, default="data/trajectories/",
                        help="Output directory for trajectory JSON files")
    parser.add_argument("--file", type=str, default=None,
                        help="Convert a single file instead of a directory")
    args = parser.parse_args()

    if args.file:
        traj = parse_hdt_game_file(args.file)
        if traj:
            out = Path(args.output) / f"{traj.game_id}.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            with open(out, "w") as f:
                json.dump(traj.to_dict(), f, indent=2)
            print(f"Converted 1 trajectory → {out}")
        else:
            print("Failed to parse game file")
    else:
        n = convert_directory(args.input, args.output)
        print(f"Converted {n} trajectories → {args.output}")


if __name__ == "__main__":
    main()
