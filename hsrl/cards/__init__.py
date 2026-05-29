"""
HSRL Cards Module

Contains all card definitions organized by type.

Philosophy reminder:
  1. Define the standard example for each mechanism
  2. Test it
  3. Then add real cards following the pattern:
     Natural Language -> Structured Description -> Function Registration
"""


def init_cards():
    """Ensure all card definitions are loaded into the global CARDS database.

    Call once before creating a Game or BattlegroundsEnv to populate the
    card registry with all minion, hero, spell, trinket, anomaly, and
    reward card definitions.
    """
    import hsrl.cards.minions.pool as _  # noqa: F401
    import hsrl.cards.minions.scripts as _  # noqa: F401
    import hsrl.cards.minions.tokens as _  # noqa: F401
    import hsrl.cards.heroes.pool as _  # noqa: F401
    import hsrl.cards.heroes.scripts as _  # noqa: F401
    import hsrl.cards.spells.scripts as _  # noqa: F401
    import hsrl.cards.trinkets.scripts as _  # noqa: F401
    import hsrl.cards.rewards.scripts as _  # noqa: F401
    import hsrl.cards.anomalies.scripts as _  # noqa: F401
