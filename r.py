import json, math, os, sys
from typing import Dict, Any
from pathlib import Path
import argparse

ITEMS_PATH = Path(__file__).parent / "configuration" / "items.json"

# Tuning knobs
TARGET_AVG_COINS_PER_ROLL = 50        # average coins payout if you sell what you roll
CRAFT_MULTIPLIER = 1.25               # premium multiplier when crafting to next evo
MUTATION_MULTIPLIER = 2.5             # multiplier vs base item for mutation worths
FALLBACK_REQUIRED = 2                 # when required is 0/None/missing
MIN_WORTH = 1
MAX_WORTH = 1_000_000                 # absolute cap to avoid absurd numbers

def clamp_int(x: float) -> int:
    return max(MIN_WORTH, min(int(math.ceil(x)), MAX_WORTH))

def load_items(path: str) -> Dict[str, Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_items(path: str, items: Dict[str, Dict[str, Any]]):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=4, ensure_ascii=False)
        f.write("\n")

def compute_spawn_worths(items: Dict[str, Dict[str, Any]]):
    # Natural spawns are items with rarity > 0
    spawnables = [(k, v) for k, v in items.items() if (v.get("rarity") or 0) > 0]
    if not spawnables:
        return
    weights = [v["rarity"] for _, v in spawnables if v.get("rarity") is not None]
    w_sum = sum(weights)
    n = len(spawnables)
    if w_sum <= 0:
        # fallback: flat worths
        for k, _ in spawnables:
            items[k]["worth"] = max(items[k].get("worth", MIN_WORTH), MIN_WORTH)
        return

    # worth_i = TARGET * (w_sum / (n * w_i)) so expected value per spin ~= TARGET
    for key, v in spawnables:
        w_i = v.get("rarity", 0)
        if w_i <= 0:
            continue
        worth = TARGET_AVG_COINS_PER_ROLL * (w_sum / (n * w_i))
        items[key]["worth"] = clamp_int(worth)

def build_prev_graph(items: Dict[str, Dict[str, Any]]):
    # Map prev -> [nexts]
    g = {}
    for name, v in items.items():
        prev = v.get("prev_evo")
        if prev:
            g.setdefault(prev, []).append(name)
    return g

def compute_chain_worths(items: Dict[str, Dict[str, Any]]):
    # Ensure evolution worths are at least required(prev)*worth(prev)*CRAFT_MULTIPLIER
    # Iterate until convergence or depth limit
    graph = build_prev_graph(items)

    # Start from roots (no prev_evo)
    roots = [name for name, v in items.items() if not v.get("prev_evo")]
    # BFS over chains
    visited = set()
    queue = list(roots)
    # Limit passes to avoid infinite loops on bad data
    passes = 0
    while queue and passes < 10000:
        passes += 1
        cur = queue.pop(0)
        visited.add(cur)
        if cur in graph:
            for nxt in graph[cur]:
                prev = cur
                prev_req = items.get(prev, {}).get("required", None)
                req = prev_req if isinstance(prev_req, (int, float)) else None
                # required for next evolution is stored on prev item in your schema
                if not req or req <= 0:
                    req = FALLBACK_REQUIRED
                prev_worth = items.get(prev, {}).get("worth", MIN_WORTH) or MIN_WORTH
                proposed = clamp_int(prev_worth * req * CRAFT_MULTIPLIER)
                # keep monotonic increase
                cur_worth = items.get(nxt, {}).get("worth", 0) or 0
                if proposed > cur_worth:
                    items[nxt]["worth"] = proposed
                queue.append(nxt)

def compute_mutation_worths(items: Dict[str, Dict[str, Any]]):
    # For each base item with mutations, set each mutation worth = base * multiplier
    for base_name, v in items.items():
        muts = v.get("mutations")
        if isinstance(muts, dict):
            base_worth = v.get("worth", MIN_WORTH) or MIN_WORTH
            for mut_key, mut_obj in muts.items():
                mut_worth = clamp_int(base_worth * MUTATION_MULTIPLIER)
                if not isinstance(mut_obj, dict):
                    muts[mut_key] = {"name": mut_key, "abbev": "", "worth": mut_worth}
                else:
                    mut_obj["worth"] = mut_worth

def increase_all_worths(items: Dict[str, Dict[str, Any]], multiplier: float) -> tuple[int, int]:
    changed_items = 0
    changed_mutations = 0

    def scale(val):
        try:
            return clamp_int(float(val) * multiplier)
        except Exception:
            return val

    for _, v in items.items():
        if isinstance(v, dict) and "worth" in v:
            old = v["worth"]
            new_val = scale(old)
            if new_val != old:
                v["worth"] = new_val
                changed_items += 1

        muts = v.get("mutations")
        if isinstance(muts, dict):
            for _, m in muts.items():
                if isinstance(m, dict) and "worth" in m:
                    oldm = m["worth"]
                    newm = scale(oldm)
                    if newm != oldm:
                        m["worth"] = newm
                        changed_mutations += 1
    return changed_items, changed_mutations

def main():
    parser = argparse.ArgumentParser(description="Increase worth of all items (and mutation variants).")
    parser.add_argument("-m", "--multiplier", type=float, default=2.0, help="Multiply all worths by this factor (default: 2.0)")
    args = parser.parse_args()

    items_path = ITEMS_PATH
    if not items_path.exists():
        alt = Path.cwd() / "configuration" / "items.json"
        if alt.exists():
            items_path = alt
        else:
            raise FileNotFoundError(f"items.json not found. Tried: {items_path} and {alt}")

    items = load_items(str(items_path))
    n_items, n_muts = increase_all_worths(items, args.multiplier)
    save_items(str(items_path), items)
    print(f"Increased worths by x{args.multiplier}. Items updated: {n_items}, Mutations updated: {n_muts}")
    print("Written to", items_path)

if __name__ == "__main__":
    main()