# 그림 없는 품목 찾기 (매주 자동 실행, 그림 비용 없음)
# 공개 시세 API에서 최근 8주 본경매 품목·품종을 모아, img/flowers 에 그림이 없는 품목을 정리합니다.
# 결과: review/그림없는품목.md (사람이 읽는 목록), tools/missing.json, 새 품목은 tools/queue.json 끝에 '설명 없음'으로 추가
import json, os, re, urllib.parse, urllib.request, datetime, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = os.path.join(ROOT, 'tools')
api = re.search(r"API_URL:\s*'([^']+)'", open(os.path.join(ROOT, 'js', 'config.js'), encoding='utf-8').read()).group(1)


def call(name, args):
    url = api + '?api=' + name + '&args=' + urllib.parse.quote(json.dumps(args, ensure_ascii=False))
    with urllib.request.urlopen(url, timeout=120) as r:
        j = json.loads(r.read())
    if not j.get('ok'):
        raise RuntimeError(j.get('error'))
    return j['data']


meta = call('getPriceIndex', [[], []])['meta']
days = [d['d'] for d in meta.get('dates', []) if d.get('m')]
seen = collections.defaultdict(lambda: {'days': set(), 'vars': collections.Counter(), 'qty': 0, 'amt': 0})
for d in days:
    for it in call('getCatalogDay', [d]).get('items', []):
        name, var = str(it[0]).strip(), str(it[1]).strip()
        if not name:
            continue
        s = seen[name]; s['days'].add(d); s['vars'][var] += 1
        try:
            s['qty'] += float(it[6] or 0); s['amt'] += float(it[7] or 0)
        except Exception:
            pass

stats = sorted([{'name': n, 'days': len(v['days']), 'qty': int(v['qty']), 'amount': int(v['amt']), 'varieties': len(v['vars'])} for n, v in seen.items()], key=lambda x: -x['amount'])
json.dump({'dates': days, 'items': stats}, open(os.path.join(T, 'item_stats.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)

imgs = {f[:-5] for f in os.listdir(os.path.join(ROOT, 'img', 'flowers')) if f.endswith('.webp')}
has = lambda n: n in imgs or any(n.startswith(i) for i in imgs if len(i) >= 2)
missing = sorted([n for n in seen if not has(n)], key=lambda n: (-len(seen[n]['days']), -seen[n]['qty']))

out = [{'name': n, 'days': len(seen[n]['days']), 'qty': int(seen[n]['qty']),
        'varieties': [v for v, _ in seen[n]['vars'].most_common(8)]} for n in missing]
json.dump(out, open(os.path.join(T, 'missing.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

q = json.load(open(os.path.join(T, 'queue.json'), encoding='utf-8'))
known = {x['name'] for x in q}
added = [n for n in missing if n not in known]
for n in added:
    q.append({'name': n, 'hint': ''})
json.dump(q, open(os.path.join(T, 'queue.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)

lines = [f'# 그림 없는 품목 ({datetime.date.today().isoformat()} 기준, 최근 본경매 {len(days)}일)', '',
         f'그림 있는 품목 {len(seen) - len(missing)}개 / 없는 품목 {len(missing)}개', '',
         '| 품목 | 경매 나온 날 | 거래량(속) | 주요 품종 |', '|---|---|---|---|']
for o in out:
    lines.append(f"| {o['name']}{' (새로 등장)' if o['name'] in added else ''} | {o['days']}일 | {o['qty']:,} | {', '.join(o['varieties'])} |")
print('\n'.join(lines))
