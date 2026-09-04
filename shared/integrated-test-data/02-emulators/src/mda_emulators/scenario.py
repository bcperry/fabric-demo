from __future__ import annotations

import copy
import json
import math
import random
from pathlib import Path
from typing import Any


def _distance(left: dict[str, float], right: dict[str, float]) -> float:
    return math.hypot(
        left["latitude"] - right["latitude"],
        left["longitude"] - right["longitude"],
    )


def assign_fictional_locations(scenario: dict[str, Any]) -> dict[str, Any]:
    """Assign stable synthetic locations to sites that do not declare one."""
    result = copy.deepcopy(scenario)
    bounds = result["location_bounds"]
    rng = random.Random(result["seed"])
    assigned: list[dict[str, float]] = []

    for site in result["sites"]:
        if "location" in site:
            assigned.append(site["location"])
            continue

        for _ in range(1_000):
            candidate = {
                "latitude": round(
                    rng.uniform(bounds["min_latitude"], bounds["max_latitude"]), 5
                ),
                "longitude": round(
                    rng.uniform(bounds["min_longitude"], bounds["max_longitude"]), 5
                ),
                "synthetic": True,
            }
            if all(
                _distance(candidate, existing)
                >= bounds["minimum_separation_degrees"]
                for existing in assigned
            ):
                site["location"] = candidate
                assigned.append(candidate)
                break
        else:
            raise ValueError(
                f"Unable to place {site['site_id']} within the configured bounds"
            )

    return result


def load_scenario(path: str | Path) -> dict[str, Any]:
    scenario_path = Path(path)
    with scenario_path.open(encoding="utf-8") as handle:
        scenario = json.load(handle)

    required = {
        "schema_version",
        "scenario_id",
        "seed",
        "time_scale",
        "classification",
        "location_bounds",
        "sites",
        "supporting_sources",
        "anomalies",
    }
    missing = required.difference(scenario)
    if missing:
        raise ValueError(f"Scenario is missing required fields: {sorted(missing)}")
    if scenario["classification"] != "SYNTHETIC_UNCLASS":
        raise ValueError("Only SYNTHETIC_UNCLASS scenarios are supported")

    site_ids = {site["site_id"] for site in scenario["sites"]}
    for source in scenario["supporting_sources"]:
        if source["site_id"] not in site_ids:
            raise ValueError(
                f"Supporting source {source['source_instance_id']} references an unknown site"
            )

    instance_ids = [
        system["instance_id"]
        for site in scenario["sites"]
        for system in site["systems"]
    ] + [
        source["source_instance_id"]
        for source in scenario["supporting_sources"]
    ]
    if len(instance_ids) != len(set(instance_ids)):
        raise ValueError("System instance IDs must be unique")

    return assign_fictional_locations(scenario)
