import json, collections, pathlib

base = pathlib.Path(__file__).parent / "configuration"
files = {
    "items": base / "items.json",
    "potions": base / "shop.json",
    "craftables": base / "crafting.json",
}

m = collections.defaultdict(list)

for category, path in files.items():
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for key, meta in data.items():
        ab = meta.get("abbev")
        if ab:
            m[ab].append(f"{category}:{key}")

dups = {ab: entries for ab, entries in m.items() if len(entries) > 1}
print(dups if dups else "NO_DUPES")