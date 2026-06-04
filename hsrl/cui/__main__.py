"""HSRL CUI — interactive Battlegrounds with curses-based live-updating UI.

Usage:
    python -m hsrl.cui                    # Default settings
    python -m hsrl.cui --seed 123         # Custom seed
    python -m hsrl.cui --max-turns 20     # Longer games
"""
from __future__ import annotations

import argparse
import curses


def main():
    parser = argparse.ArgumentParser(description="HSRL 酒馆战棋 CUI — 人工对局轨迹收集")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--max-turns", type=int, default=15, help="最大回合数")
    parser.add_argument("--output", type=str, default="data/trajectories_cli/", help="输出目录")
    args = parser.parse_args()

    from hsrl.cui.app import CursesApp
    app = CursesApp(seed=args.seed, max_turns=args.max_turns, output_dir=args.output)
    curses.wrapper(app.run)


if __name__ == "__main__":
    main()
