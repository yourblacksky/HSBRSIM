"""Content-addressed runtime version contract for HSBRSIM."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path


ENGINE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST_PATH = ENGINE_ROOT / "data" / "runtime_manifest.json"
DEFAULT_CARDDEFS_PATH = ENGINE_ROOT / "hsdata" / "CardDefs.xml"
DEFAULT_ENGINE_SOURCE_ROOT = ENGINE_ROOT / "hsrl"


class RuntimeVersionError(RuntimeError):
    """The checked-in runtime does not match its version manifest."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def engine_source_sha256(root: Path = DEFAULT_ENGINE_SOURCE_ROOT) -> str:
    """Hash executable engine sources, excluding tests and generated caches."""
    digest = hashlib.sha256()
    for path in sorted(Path(root).rglob("*.py")):
        relative = path.relative_to(root)
        if "tests" in relative.parts or "__pycache__" in relative.parts:
            continue
        digest.update(relative.as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _canonical_hash(payload) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _carddefs_build(path: Path) -> int:
    try:
        for _event, element in ET.iterparse(path, events=("start",)):
            if element.tag != "CardDefs":
                break
            return int(element.get("build", 0))
    except (ET.ParseError, OSError, ValueError) as exc:
        raise RuntimeVersionError(f"cannot read CardDefs build from {path}: {exc}") from exc
    raise RuntimeVersionError(f"CardDefs root/build missing in {path}")


def _xml_hero_power_ids(path: Path, hero_ids: set[str]) -> dict[str, str]:
    mappings = {}
    try:
        for _event, element in ET.iterparse(path, events=("end",)):
            if element.tag != "Entity":
                continue
            card_id = element.get("CardID", "")
            if card_id in hero_ids:
                for tag in element.findall("Tag"):
                    if tag.get("enumID") == "380" and tag.get("cardID"):
                        mappings[card_id] = tag.get("cardID")
                        break
            element.clear()
    except (ET.ParseError, OSError) as exc:
        raise RuntimeVersionError(f"cannot read hero mappings from CardDefs: {exc}") from exc
    return mappings


def _registry_summary() -> dict:
    from hsrl.cards.anomalies.scripts import ANOMALY_SCRIPT_REGISTRY
    from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
    from hsrl.cards.minions.scripts import SCRIPT_REGISTRY
    from hsrl.cards.rewards.scripts import QUEST_SCRIPT_REGISTRY, REWARD_SCRIPT_REGISTRY
    from hsrl.cards.spells.scripts import SPELL_SCRIPT_REGISTRY
    from hsrl.cards.trinkets.scripts import TRINKET_SCRIPT_REGISTRY

    registries = {
        "anomalies": ANOMALY_SCRIPT_REGISTRY,
        "hero_powers": HERO_POWER_SCRIPT_REGISTRY,
        "minions": SCRIPT_REGISTRY,
        "quests": QUEST_SCRIPT_REGISTRY,
        "rewards": REWARD_SCRIPT_REGISTRY,
        "spells": SPELL_SCRIPT_REGISTRY,
        "trinkets": TRINKET_SCRIPT_REGISTRY,
    }
    entries = {}
    for name, registry in registries.items():
        entries[name] = [
            [str(key), f"{value.__module__}.{value.__qualname__}"]
            for key, value in sorted(registry.items(), key=lambda item: str(item[0]))
        ]
    return {
        "sha256": _canonical_hash(entries),
        "counts": {name: len(values) for name, values in entries.items()},
    }


def _action_schema() -> dict:
    from hsrl.env import action

    constants = {
        "NUM_ACTIONS": action.NUM_ACTIONS,
        "BUY_OFFSET": action.BUY_OFFSET,
        "SELL_OFFSET": action.SELL_OFFSET,
        "PLAY_OFFSET": action.PLAY_OFFSET,
        "REFRESH": action.REFRESH,
        "UPGRADE": action.UPGRADE,
        "FREEZE": action.FREEZE,
        "HERO_POWER": action.HERO_POWER,
        "END_TURN": action.END_TURN,
        "GET_BUDDY": action.GET_BUDDY,
        "REARRANGE": action.REARRANGE,
        "SECOND_HERO_POWER": action.SECOND_HERO_POWER,
        "RESERVED_START": action.RESERVED_START,
        "modes": {mode.name: int(mode) for mode in action.ActionMode},
    }
    return {
        "version": "turn-recruit-50-v1",
        "sha256": _canonical_hash(constants),
    }


def _git_state(root: Path) -> dict:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, check=True,
            capture_output=True, text=True,
        ).stdout.strip()
        dirty = bool(subprocess.run(
            ["git", "status", "--porcelain"], cwd=root, check=True,
            capture_output=True, text=True,
        ).stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = "", None
    return {"commit": commit, "dirty": dirty}


def _git_commit(root: Path) -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, check=True,
            capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def current_runtime_manifest(path: Path = DEFAULT_MANIFEST_PATH) -> dict:
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeVersionError(f"cannot load runtime manifest {path}: {exc}") from exc
    manifest_id = manifest.get("manifest_id", "")
    payload = dict(manifest)
    payload.pop("manifest_id", None)
    expected_id = (
        f"hsbrsim-{manifest.get('patch', '')}-{_canonical_hash(payload)[:16]}"
    )
    if manifest_id != expected_id:
        raise RuntimeVersionError(
            f"runtime manifest id mismatch: {manifest_id!r} != {expected_id!r}"
        )
    return manifest


def _validate(expected: dict, carddefs_path: Path) -> dict:
    failures = []
    summary_path = ENGINE_ROOT / "data" / "bg_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if str(summary.get("patch", "")) != expected.get("patch"):
        failures.append(
            f"patch {summary.get('patch')!r} != {expected.get('patch')!r}"
        )

    for relative, expected_hash in expected.get("files", {}).items():
        path = ENGINE_ROOT / relative
        actual_hash = _sha256(path) if path.is_file() else "missing"
        if actual_hash != expected_hash:
            failures.append(f"{relative} sha256 {actual_hash} != {expected_hash}")

    expected_carddefs = expected.get("carddefs", {})
    hsdata_commit = _git_commit(ENGINE_ROOT / "hsdata")
    if hsdata_commit != expected.get("hsdata_commit"):
        failures.append(
            f"hsdata commit {hsdata_commit!r} != {expected.get('hsdata_commit')!r}"
        )
    actual_build = _carddefs_build(carddefs_path)
    actual_hash = _sha256(carddefs_path)
    if actual_build != expected_carddefs.get("build"):
        failures.append(
            f"CardDefs build {actual_build} != {expected_carddefs.get('build')}"
        )
    if actual_hash != expected_carddefs.get("sha256"):
        failures.append(
            f"CardDefs sha256 {actual_hash} != {expected_carddefs.get('sha256')}"
        )

    expected_mappings = expected.get("hero_power_mappings", {})
    actual_mappings = _xml_hero_power_ids(carddefs_path, set(expected_mappings))
    for hero_id, power_id in expected_mappings.items():
        if actual_mappings.get(hero_id) != power_id:
            failures.append(
                f"hero mapping {hero_id}={actual_mappings.get(hero_id)!r} != {power_id!r}"
            )

    registry = _registry_summary()
    if registry != expected.get("script_registry"):
        failures.append("script registry hash/counts do not match manifest")
    action_schema = _action_schema()
    if action_schema != expected.get("action_schema"):
        failures.append("action schema does not match manifest")
    expected_source = expected.get("engine_source", {})
    actual_source_hash = engine_source_sha256()
    if actual_source_hash != expected_source.get("sha256"):
        failures.append(
            "engine source sha256 "
            f"{actual_source_hash} != {expected_source.get('sha256')}"
        )

    if failures:
        raise RuntimeVersionError("runtime version mismatch: " + "; ".join(failures))
    runtime = copy.deepcopy(expected)
    runtime["engine_git"] = _git_state(ENGINE_ROOT)
    return runtime


@lru_cache(maxsize=1)
def _validate_default_cached() -> dict:
    return _validate(current_runtime_manifest(), DEFAULT_CARDDEFS_PATH)


def validate_runtime_manifest(*, expected: dict | None = None,
                              carddefs_path: Path | None = None,
                              use_cache: bool = True) -> dict:
    """Validate every versioned engine component or fail closed."""
    if expected is None and carddefs_path is None and use_cache:
        return copy.deepcopy(_validate_default_cached())
    manifest = copy.deepcopy(expected) if expected is not None else current_runtime_manifest()
    path = Path(carddefs_path) if carddefs_path is not None else DEFAULT_CARDDEFS_PATH
    return _validate(manifest, path)
