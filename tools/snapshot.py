# 시세 서버(Apps Script)에서 첫 화면에 필요한 시세를 받아 data/snapshot.json 으로 저장합니다.
# 사이트는 이 파일을 먼저 읽어 바로 보여 주고, 뒤에서 시세 서버에 더 새 시세가 있는지만 확인합니다.
# 시세가 바뀌지 않았으면 파일을 다시 쓰지 않습니다 (쓸데없는 커밋 방지).
import json, os, re, sys, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'snapshot.json')
cfg = open(os.path.join(ROOT, 'js', 'config.js'), encoding='utf-8').read()
API = re.search(r"https://script\.google\.com/macros/s/[^'\"]+/exec", cfg).group(0)


def call(name, *args, tries=3):
    q = {'api': name}
    if args:
        q['args'] = json.dumps(list(args), ensure_ascii=False)
    url = API + '?' + urllib.parse.urlencode(q)
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'kkot-sise-snapshot'}), timeout=60) as r:
                j = json.loads(r.read().decode('utf-8'))
            if not j.get('ok'):
                raise RuntimeError(j.get('error'))
            return j['data']
        except Exception as e:  # 잠깐 실패하면 다시 시도
            last = e
            time.sleep(3 * (i + 1))
    raise RuntimeError(f'{name} 실패: {last}')


dash = call('getDashboardData')
if not (dash or {}).get('rows'):
    sys.exit('대시보드 자료가 비어 있어 저장하지 않습니다')
index = call('getPriceIndex', [], [])  # 키를 비우면 모든 품목·품종을 돌려줍니다
index['grades'] = {}
try:
    news = call('getFlowerNews')
except Exception as e:
    news = None
    print('뉴스 건너뜀:', e)
cat = None
latest = (index.get('meta') or {}).get('latestDate')
if latest:
    try:
        cat = call('getCatalogDay', latest)
    except Exception as e:
        print('전체 품목 건너뜀:', e)

snap = {'dashboard': dash, 'index': index, 'news': news, 'catalog': cat}
old = None
if os.path.exists(OUT):
    try:
        old = json.load(open(OUT, encoding='utf-8'))
    except Exception:
        old = None


def core(s):  # 시각 표시(fetchedAt 등)를 빼고 실제 시세가 바뀌었는지 비교
    if not s:
        return None
    d = dict(s.get('dashboard') or {})
    for k in ('fetchedAt',):
        d.pop(k, None)
    return json.dumps([d, (s.get('index') or {}).get('meta', {}).get('builtAt'), (s.get('index') or {}).get('rows'),
                       s.get('news'), (s.get('catalog') or {}).get('date'), len((s.get('catalog') or {}).get('items') or [])],
                      ensure_ascii=False, sort_keys=True)


if old and core(old) == core(snap):
    print('바뀐 시세 없음')
    sys.exit(0)
snap['at'] = time.strftime('%Y-%m-%dT%H:%M:%S+09:00', time.gmtime(time.time() + 9 * 3600))
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(snap, f, ensure_ascii=False, separators=(',', ':'))
print('저장', snap['at'], index.get('meta', {}).get('builtAt'), round(os.path.getsize(OUT) / 1024), 'KB')
