# 밤마다 꽃 그림을 자동으로 만드는 스크립트 (GitHub Actions에서 실행)
# 1) tools/queue.json 순서대로 아직 안 만든 꽃을 N개 고름 (설명(hint)이 비어 있으면 '확인 필요'로 건너뜀)
# 2) 승인된 그림 몇 장을 견본으로 보여 주며 같은 그림체로 그려 달라고 OpenAI에 주문
# 3) tools/process_flower.py 로 체크무늬·번짐 정리 → img/flowers/<이름>.webp
# 4) tools/state.json 에 기록, 미리보기 페이지의 그림 목록과 버전 갱신, 검수용 모아 보기 이미지 생성
import base64, datetime, json, os, re, subprocess, sys, time, urllib.parse, urllib.request, urllib.error, uuid

import builtins
_LOG=[]
_p=builtins.print
def print(*a,**k):
    _LOG.append(' '.join(str(x) for x in a)); _p(*a,**k)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = os.path.join(ROOT, 'tools')
KEY = os.environ.get('OPENAI_API_KEY', '')
N = int(os.environ.get('PER_RUN', '10'))
ONLY = [x for x in os.environ.get('ONLY', '').split(',') if x.strip()]
QUALITY = os.environ.get('QUALITY', 'medium')
MODELS = [m for m in os.environ.get('MODELS', 'gpt-image-2.5-sunburst,gpt-image-2.5-flare,gpt-image-2,gpt-image-1').split(',') if m]
REFS = ['금꿩의다리', '국화', '리시안사스', '스타티스']

PROMPT = """다음 식물을 제작한다: {name}
식물 특징(실제 외형 기준): {hint}

{photo_note}첨부한 그림 견본들과 같은 그림체(사실적인 압화 질감, 바랜 빈티지 색감, 종이 질감)로 같은 시리즈처럼 만든다. 단, 견본의 장식 배치(가운데 테이프+밀랍 인장, 오른쪽 우표 카드 같은 구성)는 따라 하지 않는다. 그림 견본 속 꽃을 그리지 말고, 위 식물만 그린다.

이번 그림의 장식은 아래대로 한다. 사람이 손으로 꾸민 것처럼 살짝 삐뚤고 자연스럽게, 매번 같은 틀처럼 보이지 않게:
{recipe}

위 식물을 실제 식물 특징에 맞게 표현한 빈티지 압화 콜라주 이미지를 만든다. 꽃 모양, 잎 모양, 줄기 형태를 실제와 가깝게 반영한다.

스타일은 사실적인 꽃과 압화의 질감이 느껴지는 빈티지 보태니컬 스크랩북 무드로 한다. 꽃 뒤에는 찢어진 크라프트지, 낡은 영자신문 조각, 손글씨 종이, 오래된 서류 조각을 소량만 겹친다. 장식 소품은 위 '이번 그림의 장식'에 적힌 것만 쓴다. 식물 도감처럼 딱딱하게 나열하지 말고, 실제로 손으로 꾸민 빈티지 압화 다꾸처럼 보이되, 식물 자체는 정확하고 우아하게 중심을 잡아야 한다.

중요한 구성 규칙:
- 꽃/잎/줄기가 주인공이어야 한다.
- 세로로 긴 구도에 꽃부터 줄기 끝까지 다 보이게 한다.
- 꽃의 일부와 잎, 줄기는 종이 바깥으로 자연스럽게 벗어나와야 한다.
- 종이는 1~3장 정도의 조각으로 절제해 사용하고, 꽃 전체 뒤를 빽빽하게 채우지 않는다.
- 위 고정 방법으로 꽃이 종이에 실제로 붙어(묶여) 있는 듯 보여야 한다.
- 꽃이 그냥 종이 위에 놓인 느낌이 아니라, 종이에 고정된 압화 다꾸 느낌이어야 한다.
- 디자인적으로 균형감 있고 아름답게 구성한다.

색감은 전체적으로 따뜻하고 차분한 빈티지 톤으로 한다. 채도는 낮추고, 압화처럼 약간 바랜 색감으로 표현한다. 너무 쨍한 색, 형광빛, 강한 대비는 금지한다.

절대 넣지 말 것: 두껍고 지저분한 흰 외곽선, 폴라로이드 프레임, 완전한 직사각형 배경 카드, 체크무늬 배경처럼 보이는 표현, 꽃보다 더 눈에 띄는 과한 배경 종이, 줄기에 불필요한 붉은 갈색 반점, 글자로 된 이름표.

배경은 완전히 투명하게 한다.{bg_extra}"""

BUNDLE_EXTRA = "\n이 품목은 꽃 한 종류가 아니라 여러 종류를 섞은 묶음이다. 위 설명의 재료들을 한 다발로 묶어 표현한다."


def multipart(fields, files):
    b = uuid.uuid4().hex
    out = []
    for k, v in fields:
        out += [f'--{b}', f'Content-Disposition: form-data; name="{k}"', '', str(v)]
    body = '\r\n'.join(out).encode() + b'\r\n'
    for k, fn, data, ct in files:
        body += f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{fn}"\r\nContent-Type: {ct}\r\n\r\n'.encode() + data + b'\r\n'
    body += f'--{b}--\r\n'.encode()
    return body, f'multipart/form-data; boundary={b}'


import random

FIX = ['줄기 아래쪽을 마스킹테이프 한 줄로 비스듬히 가로질러 붙임',
       '마스킹테이프 두 조각을 X자로 엇갈려 줄기를 고정',
       '짧게 손으로 찢은 마스킹테이프 조각 3개를 줄기와 잎 여기저기에 삐뚤게 붙임',
       '줄기를 마끈으로 두세 번 감아 리본 없이 매듭만 짓고, 매듭 위에 작은 테이프 조각',
       '줄기를 얇은 레이스 리본으로 묶고, 종이에는 테이프 한 조각만',
       '종이에 칼집을 낸 틈으로 줄기를 끼워 넣은 것처럼 표현하고 테이프는 한쪽 끝에만',
       '투명 셀로판 테이프 한 줄로 줄기를 붙여 테이프 가장자리만 살짝 반짝임',
       '종이 클립(빈티지 황동 클립) 하나로 줄기를 종이에 집어 둠']
TAPE = ['무지', '작은 체크무늬', '작은 도트', '가는 줄무늬', '잔꽃무늬', '영문 손글씨 무늬', '격자무늬', '레이스 무늬', '반투명 와시']
TAPE_COLOR = ['두 테이프 모두 꽃 색과 같은 계열의 바랜 톤 (한 장은 진하게, 한 장은 연하게)',
              '한 장은 꽃 색과 같은 계열의 바랜 톤, 다른 한 장은 베이지·크라프트 같은 중립색',
              '한 장은 꽃 색과 같은 계열, 다른 한 장은 잎 색에 맞춘 세이지그린 계열',
              '한 장은 꽃 색과 같은 계열, 다른 한 장은 꽃 색과 은은하게 어울리는 보색 계열의 아주 연한 톤']
EXTRA = ['밀랍 인장 하나 (색은 꽃 색에 맞추고 테이프 위가 아닌 종이 모서리 쪽에)',
         '빈티지 우표 한 장 (톱니가 한쪽 살짝 찢어지고 소인이 반쯤 찍힌)',
         '작은 종이 꼬리표(태그)에 마끈이 달려 있는 것',
         '오래된 영수증이나 도서관 대출 카드 조각',
         '흐릿한 날짜 고무도장 자국',
         '손글씨로 짧게 끄적인 메모 쪽지 (읽히지 않는 필기체)',
         '압화 꽃잎 두세 장이 흩어져 붙음',
         '구멍 뚫린 바인더 종이 조각',
         '얇은 트레이싱지 한 장이 꽃 일부를 반쯤 덮음',
         '작은 단추 하나']
LAYOUT = ['꽃다발을 왼쪽으로 10도쯤 기울여 배치', '꽃다발을 오른쪽으로 살짝 기울여 배치', '줄기를 거의 똑바로 세우고 종이 조각은 한쪽으로 치우치게',
          '종이 조각을 위쪽 뒤에 두고 줄기 아래는 종이 밖으로 길게 나오게', '종이 조각 2장을 엇갈려 겹치고 꽃은 그 모서리에 걸치게']


def deco_recipe(name):
    r = random.Random('kkot-' + name)
    parts = [r.choice(LAYOUT), '고정 방법: ' + r.choice(FIX), '테이프 무늬: ' + ', '.join(r.sample(TAPE, 2)), '테이프 색: ' + r.choice(TAPE_COLOR) + ' (테이프가 꽃보다 튀지 않게 채도 낮게)']
    k = r.choice([0, 1, 1, 2])
    if k:
        parts.append('곁들일 소품: ' + ' / '.join(r.sample(EXTRA, k)))
    else:
        parts.append('곁들일 소품: 없음 (종이와 테이프만으로 담백하게)')
    return '\n'.join('- ' + x for x in parts)


UA = {'User-Agent': 'kkot-sise-flower-bot/1.0 (https://verdus927.github.io/kkot-sise/)'}


def sci_name(hint):
    m = re.search(r'\(([A-Z][a-z]+(?: x)? [a-z][a-z\-]+)', hint)
    if m:
        return m.group(1)
    m = re.search(r'\b([A-Z][a-z]+(?: x)? [a-z][a-z\-]+)\b', hint)
    if m and m.group(1).split()[-1] not in ('type', 'florist', 'filler', 'leaf', 'branch'):
        return m.group(1)
    m = re.search(r'\b([A-Z][a-z]{3,})\b', hint)
    return m.group(1) if m else ''


def get_json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
        return json.loads(r.read())


def fetch_photos(hint, k=2, sci=''):
    # 실제 식물 사진: 위키백과 대표 사진 + 위키미디어 공용 검색 (자유 이용 사진)
    q = sci or sci_name(hint)
    if not q:
        return [], ''
    urls = []
    try:
        j = get_json('https://en.wikipedia.org/w/api.php?action=query&prop=pageimages&piprop=thumbnail&pithumbsize=768&redirects=1&format=json&titles=' + urllib.parse.quote(q))
        for pg in j.get('query', {}).get('pages', {}).values():
            t = pg.get('thumbnail', {}).get('source')
            if t and not t.lower().endswith('.svg.png'):
                urls.append(t)
    except Exception as e:
        print('  사진(위키백과) 실패', q, e)
    try:
        j = get_json('https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrnamespace=6&gsrlimit=8&prop=imageinfo&iiprop=url|mime&iiurlwidth=768&format=json&gsrsearch=' + urllib.parse.quote(q + ' flower'))
        pages = sorted(j.get('query', {}).get('pages', {}).values(), key=lambda p: p.get('index', 99))
        for pg in pages:
            ii = (pg.get('imageinfo') or [{}])[0]
            if ii.get('mime') == 'image/jpeg' and ii.get('thumburl') and ii['thumburl'] not in urls:
                urls.append(ii['thumburl'])
    except Exception as e:
        print('  사진(공용) 실패', q, e)
    out = []
    for u in urls[:k]:
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40) as r:
                out.append(r.read())
        except Exception as e:
            print('  사진 받기 실패', u, e)
    return out, q


def call(model, prompt, transparent, photos=()):
    fields = [('model', model), ('prompt', prompt), ('size', '1024x1536'), ('quality', QUALITY), ('n', '1')]
    if transparent:
        fields += [('background', 'transparent'), ('output_format', 'png')]
    files = [('image[]', f'photo{i}.jpg', b, 'image/jpeg') for i, b in enumerate(photos)]
    for r in REFS[:max(1, 5 - len(photos))]:
        p = os.path.join(ROOT, 'img', 'flowers', r + '.webp')
        if os.path.exists(p):
            files.append(('image[]', f'ref{len(files)}.webp', open(p, 'rb').read(), 'image/webp'))
    body, ct = multipart(fields, files)
    req = urllib.request.Request('https://api.openai.com/v1/images/edits', data=body, method='POST',
                                 headers={'Authorization': f'Bearer {KEY}', 'Content-Type': ct})
    with urllib.request.urlopen(req, timeout=600) as res:
        j = json.loads(res.read())
    return base64.b64decode(j['data'][0]['b64_json']), j.get('usage')


def remove_flat_bg(path):
    # 투명 배경이 안 되는 모델일 때: 가장자리와 이어진 흰/연한 단색 배경을 지움
    from PIL import Image
    import numpy as np
    from scipy import ndimage
    im = np.array(Image.open(path).convert('RGBA')).astype(int)
    rgb = im[:, :, :3]
    edge = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    bgc = np.median(edge, axis=0)
    near = np.abs(rgb - bgc).max(2) < 18
    seed = np.zeros_like(near); seed[0, :] = seed[-1, :] = seed[:, 0] = seed[:, -1] = True
    bg = ndimage.binary_propagation(seed & near, mask=near)
    im[:, :, 3] = np.where(bg, 0, im[:, :, 3])
    Image.fromarray(im.astype('uint8'), 'RGBA').save(path)


def main():
    if not KEY:
        print('OPENAI_API_KEY 없음'); return finish([], {}, os.path.join(T, 'state.json'))
    queue = json.load(open(os.path.join(T, 'queue.json'), encoding='utf-8'))
    sp = os.path.join(T, 'state.json')
    state = json.load(open(sp, encoding='utf-8')) if os.path.exists(sp) else {}
    todo = [q for q in queue if q['hint'] and (q['name'] in ONLY if ONLY else q['name'] not in state)][:N]
    if not todo:
        print('할 일 없음', ONLY); return finish([], state, sp)
    raw = os.path.join(T, 'raw'); os.makedirs(raw, exist_ok=True)
    made = []
    model_ok = None
    for q in todo:
        name = q['name']
        photos, sq = fetch_photos(q['hint'], sci=q.get('sci', '')) if not q['hint'].startswith('BUNDLE') else ([], '')
        print(f'{name}: 실제 사진 {len(photos)}장 ({sq})')
        if photos:
            os.makedirs(os.path.join(T, 'photos'), exist_ok=True); open(os.path.join(T, 'photos', name + '.jpg'), 'wb').write(photos[0])
        note = (f'첨부 이미지 중 처음 {len(photos)}장은 이 식물({sq})의 실제 사진이다. 꽃·잎·줄기 모양과 색은 이 사진을 기준으로 정확하게 따른다. 나머지 이미지는 그림체 견본이다.\n') if photos else ''
        prompt = PROMPT.format(recipe=deco_recipe(name), photo_note=note, name=name, hint=q['hint'], bg_extra=BUNDLE_EXTRA if q['hint'].startswith('BUNDLE') else '')
        img, used, transparent = None, None, True
        for m in ([model_ok] if model_ok else MODELS):
            for tr in (True, False):
                try:
                    p = prompt if tr else prompt.replace('배경은 완전히 투명하게 한다.', '배경은 아무것도 없는 단색 흰색으로만 채운다.')
                    img, usage = call(m, p, tr, photos)
                    used, transparent = m, tr
                    break
                except urllib.error.HTTPError as e:
                    msg = e.read().decode('utf-8', 'ignore')[:300]
                    print(f'  {name} / {m} / 투명={tr}: {e.code} {msg}')
                    if e.code == 401 or (e.code == 429 and ('quota' in msg.lower() or 'billing' in msg.lower())):
                        print('키 오류 또는 잔액 부족: 여기서 멈춤'); return finish(made, state, sp)
                    if e.code == 400 and 'transparent' in msg.lower():
                        continue
                    break
                except Exception as e:
                    print(f'  {name} / {m}: {e}'); break
            if img:
                model_ok = m; break
        if not img:
            print(f'{name}: 실패'); continue
        rp = os.path.join(raw, name + '.png'); open(rp, 'wb').write(img)
        if not transparent:
            remove_flat_bg(rp)
        subprocess.run([sys.executable, os.path.join(T, 'process_flower.py'), os.path.join(ROOT, 'img', 'flowers'), f'{name}={rp}'], check=True)
        state[name] = {'date': datetime.date.today().isoformat(), 'model': used, 'transparent': transparent, 'status': '검수 대기'}
        made.append(name)
        print(f'{name}: 완료 ({used}, 투명={transparent})')
        time.sleep(2)
    finish(made, state, sp)


def finish(made, state, sp):
    open(os.path.join(T, 'last_run.log'), 'w', encoding='utf-8').write(datetime.datetime.now().isoformat() + '\n' + '\n'.join(_LOG) + '\n')
    json.dump(state, open(sp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if not made:
        return
    # 미리보기 페이지: 그림 목록과 그림 버전 갱신
    for page in ['preview/index.html', 'index.html']:
        p = os.path.join(ROOT, page)
        s = open(p, encoding='utf-8').read()
        m = re.search(r'const FLOWER_IMG=new Set\((\[[^\]]*\])\);', s)
        if not m:
            continue
        cur = json.loads(m.group(1))
        cur += [n for n in made if n not in cur]
        s = s.replace(m.group(0), 'const FLOWER_IMG=new Set(' + json.dumps(cur, ensure_ascii=False) + ');')
        s = re.sub(r"const IMG_V='[^']*'", "const IMG_V='" + datetime.datetime.now().strftime('%Y%m%d%H%M') + "'", s)
        open(p, 'w', encoding='utf-8').write(s)
    # 검수용 모아 보기 (흰색·어두운색·크라프트 배경)
    from PIL import Image, ImageDraw
    tiles = []
    for n in made:
        im = Image.open(os.path.join(ROOT, 'img', 'flowers', n + '.webp')).convert('RGBA'); im.thumbnail((260, 380))
        row = Image.new('RGB', (1120, 400), (250, 246, 238))
        php = os.path.join(T, 'photos', n + '.jpg')
        if os.path.exists(php):
            ph = Image.open(php).convert('RGB'); ph.thumbnail((270, 390)); row.paste(ph, (5 + (270 - ph.width) // 2, (400 - ph.height) // 2))
        try:
            from PIL import ImageFont; fnt = ImageFont.truetype('/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf', 22)
        except Exception:
            fnt = None
        ImageDraw.Draw(row).text((12, 10), n, fill=(60, 50, 40), font=fnt)
        for j, c in enumerate([(255, 255, 255), (40, 38, 36), (185, 133, 73)]):
            bg = Image.new('RGBA', (280, 400), c + (255,)); bg.alpha_composite(im, ((280 - im.width) // 2, (400 - im.height) // 2))
            row.paste(bg.convert('RGB'), (280 + j * 280, 0))
        tiles.append(row)
    sheet = Image.new('RGB', (1120, 400 * len(tiles)))
    for i, t in enumerate(tiles):
        sheet.paste(t, (0, 400 * i))
    os.makedirs(os.path.join(ROOT, 'review'), exist_ok=True)
    day = datetime.date.today().isoformat()
    sheet.save(os.path.join(ROOT, 'review', f'{day}.jpg'), quality=82)
    lst = os.path.join(ROOT, 'review', 'latest.json')
    json.dump({'date': day, 'names': made}, open(lst, 'w', encoding='utf-8'), ensure_ascii=False)


if __name__ == '__main__':
    main()
