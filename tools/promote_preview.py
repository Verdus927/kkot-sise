# 미리보기(preview/index.html)를 본판(index.html)으로 옮깁니다. 경로만 본판 위치에 맞게 바꿉니다.
import os, shutil
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(ROOT, 'preview/index.html'), encoding='utf-8').read()
s = s.replace("navigator.serviceWorker.register('../sw.js',{scope:'../'})", "navigator.serviceWorker.register('sw.js',{scope:'./'})")
s = s.replace('src="collage.webp"', 'src="img/collage.webp"')
s = s.replace('<!-- 꽃 콜라주 그림: preview/collage.webp 를 바꾸면 그림이 바뀝니다 -->', '<!-- 꽃 콜라주 그림: img/collage.webp 를 바꾸면 그림이 바뀝니다 -->')
s = s.replace('content="https://verdus927.github.io/kkot-sise/preview/"', 'content="https://verdus927.github.io/kkot-sise/"')
s = s.replace('../', '')
open(os.path.join(ROOT, 'index.html'), 'w', encoding='utf-8').write(s)
shutil.copyfile(os.path.join(ROOT, 'preview/collage.webp'), os.path.join(ROOT, 'img/collage.webp'))
print('본판으로 옮김')
