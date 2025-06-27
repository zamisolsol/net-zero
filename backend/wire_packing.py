# wire_packing.py  ─ 파이썬 3.8+
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Line3DCollection
from functools import lru_cache
from typing import List, Tuple, FrozenSet

Dim = Tuple[int, int, int]            # (w,d,h)
Placement = Tuple[int, Dim, Tuple[int, int, int]]   # (idx, size, pos)

# ────────────────── DP + 좌표 구하기 (변경 없음) ──────────────────
def rotations(dim):  # … (위에서 쓰던 그대로)
    w,d,h = dim; return [(w,d,h),(w,h,d),(d,w,h),(d,h,w),(h,w,d),(h,d,w)]
def merge(a,b,ax): w1,d1,h1=a; w2,d2,h2=b; return (
    (w1+w2,max(d1,d2),max(h1,h2)) if ax==0 else
    (max(w1,w2),d1+d2,max(h1,h2)) if ax==1 else
    (max(w1,w2),max(d1,d2),h1+h2))
def pareto(fs):
    keep=[]
    for dims,pl in fs:
        w,d,h=dims; bad=False; i=len(keep)-1
        while i>=0:
            kw,kd,kh=keep[i][0]
            if kw<=w and kd<=d and kh<=h: bad=True; break
            if w<=kw and d<=kd and h<=kh: keep.pop(i)
            i-=1
        if not bad: keep.append((dims,pl))
    return frozenset(keep)
def solve(items:List[Dim]):
    n,s= len(items),tuple(items)
    @lru_cache(None)
    def dp(mask:int)->FrozenSet[Tuple[Dim,Tuple[Placement,...]]]:
        if mask&(mask-1)==0:
            i=mask.bit_length()-1
            return frozenset((r,((i,r,(0,0,0)),)) for r in rotations(s[i]))
        cand=[]
        sub=mask
        while sub:
            sub=(sub-1)&mask; A,B=sub,mask^sub
            if not A or not B or (A & -A)>(B & -B): continue
            for dA,pA in dp(A):
                for dB,pB in dp(B):
                    for ax in range(3):
                        shift=(dA[0] if ax==0 else 0,
                               dA[1] if ax==1 else 0,
                               dA[2] if ax==2 else 0)
                        pB2=tuple((k,d,(x+shift[0],y+shift[1],z+shift[2]))
                                  for k,d,(x,y,z) in pB)
                        cand.append((merge(dA,dB,ax),pA+pB2))
        return pareto(cand)
    return min(dp((1<<len(items))-1),
               key=lambda x:x[0][0]*x[0][1]*x[0][2])

# ────────────────── 3-D 와이어프레임 그리기 ──────────────────
def draw_wire(placements:Tuple[Placement,...], box:Dim):
    fig=plt.figure(); ax=fig.add_subplot(111,projection='3d')
    def lines(origin,size):
        x0,y0,z0=origin; w,d,h=size
        pts=[(x0,y0,z0),(x0+w,y0,z0),(x0+w,y0+d,z0),(x0,y0+d,z0),
             (x0,y0,z0+h),(x0+w,y0,z0+h),(x0+w,y0+d,z0+h),(x0,y0+d,z0+h)]
        edges=[(0,1),(1,2),(2,3),(3,0),
               (4,5),(5,6),(6,7),(7,4),
               (0,4),(1,5),(2,6),(3,7)]
        return [[pts[i],pts[j]] for i,j in edges]
    segs=[]
    for _,dim,pos in placements: segs+=lines(pos,dim)
    # 컨테이너(점선)
    segs+=lines((0,0,0),box)
    lc=Line3DCollection(segs,colors='k',linewidths=1)
    ax.add_collection3d(lc)
    W,D,H=box; ax.set_xlim(0,W); ax.set_ylim(0,D); ax.set_zlim(0,H)
    ax.set_box_aspect([W,D,H])
    ax.set_xlabel('X'); ax.set_ylabel('Y'); ax.set_zlabel('Z')
    plt.title('3-D Packing (wireframe)'); plt.tight_layout(); plt.show()


import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import matplotlib.cm as cm
import numpy as np

def draw_wire(placements: Tuple[Placement, ...], box: Dim, save_path=None):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    def get_box_faces(origin, size):
        x0, y0, z0 = origin
        w, d, h = size
        x1, y1, z1 = x0 + w, y0 + d, z0 + h

        # 8 corners
        pts = np.array([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
                        [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]])
        # 6 faces
        faces = [
            [pts[0], pts[1], pts[2], pts[3]],  # bottom
            [pts[4], pts[5], pts[6], pts[7]],  # top
            [pts[0], pts[1], pts[5], pts[4]],  # front
            [pts[2], pts[3], pts[7], pts[6]],  # back
            [pts[1], pts[2], pts[6], pts[5]],  # right
            [pts[3], pts[0], pts[4], pts[7]],  # left
        ]
        return faces
    
    

    # 색상 팔레트
    cmap = cm.get_cmap('tab20', len(placements))

    # 각 아이템 박스 (투명한 solid)
    for i, (_, dim, pos) in enumerate(placements):
        faces = get_box_faces(pos, dim)
        color = cmap(i)
        poly = Poly3DCollection(faces, facecolors=color, edgecolors='k', linewidths=0.5, alpha=0.6)
        ax.add_collection3d(poly)

    # 컨테이너 외곽 (점선 wireframe)
    def draw_container_edges(origin, size):
        x0, y0, z0 = origin
        w, d, h = size
        pts = [(x0,y0,z0),(x0+w,y0,z0),(x0+w,y0+d,z0),(x0,y0+d,z0),
               (x0,y0,z0+h),(x0+w,y0,z0+h),(x0+w,y0+d,z0+h),(x0,y0+d,z0+h)]
        edges = [(0,1),(1,2),(2,3),(3,0),
                 (4,5),(5,6),(6,7),(7,4),
                 (0,4),(1,5),(2,6),(3,7)]
        for i,j in edges:
            ax.plot(*zip(pts[i], pts[j]), color='black', linestyle='dotted', alpha=0.4)

    draw_container_edges((0, 0, 0), box)

    W, D, H = box
    ax.set_xlim(0, W)
    ax.set_ylim(0, D)
    ax.set_zlim(0, H)
    ax.set_box_aspect([W, D, H])
    ax.set_xlabel('X'); ax.set_ylabel('Y'); ax.set_zlabel('Z')
    plt.title('3D Packing (solid with transparency)')
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path)
        plt.close()
    else:
        plt.show()


