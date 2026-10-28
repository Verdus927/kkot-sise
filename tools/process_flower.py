# 사용법: python3 process_flower.py <출력폴더> <이름=파일경로> ...
# 1) 투명 배경 검사 (가짜 체크무늬 포함)  2) 가장자리 색 번짐 정리  3) 사이트용 webp 저장
import sys
from PIL import Image
import numpy as np
from scipy import ndimage
out=sys.argv[1]
for arg in sys.argv[2:]:
    name,path=arg.split('=',1)
    im=Image.open(path).convert('RGBA');a=np.array(im).astype(float)
    alpha=a[:,:,3]
    transp=(alpha<10).mean()
    verdict='OK'
    if transp<0.05:
        # 알파가 거의 없으면: 가장자리에 체크무늬(회색/흰색 번갈아)가 그려진 가짜 투명인지 확인
        edge=np.concatenate([a[:20,:,:3].reshape(-1,3),a[-20:,:,:3].reshape(-1,3)])
        sat=(edge.max(1)-edge.min(1)).mean()
        verdict='가짜 투명(체크무늬 그림)' if sat<12 else '배경 있음'
    rgbi=a[:,:,:3];sat=rgbi.max(2)-rgbi.min(2);lum=rgbi.mean(2)
    # 투명한 곳 밑에 체크무늬가 깔려 있는지(칸 크기 p) 먼저 확인. 없으면 체크무늬 정리는 건너뜀 (흰 꽃잎 보호)
    L=lum;bgL=alpha<20
    best=(0,0)
    for p in range(3,40):
        m1=bgL[:,p:]&bgL[:,:-p];m2=bgL[:,2*p:]&bgL[:,:-2*p]
        if m1.sum()<1000 or m2.sum()<1000: continue
        sc=np.abs(L[:,p:]-L[:,:-p])[m1].mean()-np.abs(L[:,2*p:]-L[:,:-2*p])[m2].mean()
        if sc>best[0]: best=(sc,p)
    if best[0]>15:
        # 배경과 이어진 체크무늬 색 찌꺼기 제거
        bv=rgbi[bgL];bl=bv.mean(1);tn=[bv[bl<np.median(bl)].mean(0),bv[bl>=np.median(bl)].mean(0)]
        nearT=np.zeros_like(alpha,bool)
        for t in tn: nearT|=np.abs(rgbi-t).max(2)<14
        bgm=alpha<20
        junk=ndimage.binary_propagation(bgm,mask=bgm|(nearT&(sat<14)))&~bgm
        junk=ndimage.binary_dilation(junk,iterations=1)&(sat<22)&nearT
        alpha[junk]=0
    if best[0]>15:
        p=best[1];H,W=L.shape
        def sh(dx,dy):
            o=np.full_like(L,np.nan);ys=slice(max(dy,0),H+min(dy,0));yd=slice(max(-dy,0),H+min(-dy,0));xs=slice(max(dx,0),W+min(dx,0));xd=slice(max(-dx,0),W+min(-dx,0));o[yd,xd]=L[ys,xs];return o
        alt=np.zeros_like(L,bool)
        for dx,dy in [(p,0),(-p,0),(0,p),(0,-p)]:
            a1=np.abs(L-sh(dx,dy));a2=np.abs(L-sh(2*dx,2*dy))
            alt|=(np.nan_to_num(a1)>25)&(np.nan_to_num(a2,nan=99)<10)
        cand=alt&(sat<22)&(lum>120)&~bgL
        cand=ndimage.binary_closing(cand,iterations=p//2)&(sat<22)&(lum>110)
        lab2,n2=ndimage.label(cand)
        if n2:
            sz=ndimage.sum(np.ones_like(L),lab2,range(1,n2+1));kill=np.isin(lab2,1+np.where(sz>4*p*p)[0])
            alpha[kill]=0
    # 배경 체크무늬의 두 색(밝은 회색·흰색)과 거의 같은 색이 뭉친 곳은 찌꺼기로 보고 지움
    bgv=a[:,:,:3][alpha<20]
    if len(bgv)>5000 and best[0]>15:
        bl=bgv.mean(1);tones=[bgv[bl<np.median(bl)].mean(0),bgv[bl>=np.median(bl)].mean(0)]
        if all((t.max()-t.min())<12 for t in tones) and abs(tones[0].mean()-tones[1].mean())>20:
            n0=(np.abs(a[:,:,:3]-tones[0]).max(2)<13)&(alpha>0)
            n1=(np.abs(a[:,:,:3]-tones[1]).max(2)<13)&(alpha>0)
            cl=ndimage.binary_closing(n0|n1,iterations=3)
            lab3,n3=ndimage.label(cl)
            if n3:
                rng=range(1,n3+1)
                tot=ndimage.sum(np.ones_like(alpha),lab3,rng);h0=ndimage.sum(n0,lab3,rng);h1=ndimage.sum(n1,lab3,rng)
                # 체크무늬는 두 색이 함께 섞여 있어야 함 (흰 꽃잎처럼 한 색만 있으면 지우지 않음)
                ok=(tot>30)&((h0+h1)/np.maximum(tot,1)>0.45)&(np.minimum(h0,h1)/np.maximum(tot,1)>0.15)
                # 체크무늬처럼 칸 크기마다 밝기가 번갈아 바뀌는 곳만 (꽃잎의 부드러운 명암은 제외)
                pp=best[1];Lf=a[:,:,:3].mean(2)
                alt=np.zeros_like(alpha,bool)
                alt[:,pp:]|=np.abs(Lf[:,pp:]-Lf[:,:-pp])>25
                alt[pp:,:]|=np.abs(Lf[pp:,:]-Lf[:-pp,:])>25
                ar=ndimage.sum(alt&(n0|n1),lab3,rng)/np.maximum(h0+h1,1)
                ok&=ar>0.35
                alpha[np.isin(lab3,1+np.where(ok)[0])]=0
    lab,n=ndimage.label(alpha>20)
    if n>1:
        sizes=ndimage.sum(np.ones_like(alpha),lab,range(1,n+1));small=np.isin(lab,1+np.where(sizes<150)[0]);alpha[small]=0
    a[:,:,3]=alpha
    # 반투명 가장자리의 색을 안쪽 불투명 색으로 채워 흰/회색 번짐 제거
    solid=alpha>230
    idx=ndimage.distance_transform_edt(~solid,return_distances=False,return_indices=True)
    rgb=a[:,:,:3].copy();fix=(alpha<=230)
    rgb[fix]=a[:,:,:3][idx[0][fix],idx[1][fix]]
    a[:,:,:3]=rgb
    img=Image.fromarray(a.clip(0,255).astype(np.uint8),'RGBA')
    bb=img.getchannel('A').point(lambda v:255 if v>10 else 0).getbbox();img=img.crop(bb)
    import os
    if os.environ.get('ARCHIVE'): img.save(os.path.join(os.environ['ARCHIVE'],name+'.png'),optimize=True)
    img.thumbnail((420,520));img.save(f'{out}/{name}.webp','WEBP',quality=85,method=6)
    print(f'{name}: 투명 {transp*100:.0f}% · {verdict} · 저장 {img.size}')
