import json,collections
d=json.load(open('configuration/items.json'))
m=collections.defaultdict(list)
[m[v.get('abbev')].append(k) for k,v in d.items() if v.get('abbev')]
dups={k:v for k,v in m.items() if len(v)>1};print(dups if dups else 'NO_DUPES')
