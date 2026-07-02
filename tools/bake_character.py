"""리깅 캐릭터(glb)를 턴테이블 스프라이트(RGBA PNG)로 굽는다.

GPU/QtQuick3D 없이 numpy 소프트웨어 래스터라이저(z-버퍼 + 텍스처 +
디퓨즈 셰이딩)로 오프라인 렌더링 → 앱은 이미지를 순환 재생만 하면 되므로
어떤 기기에서도 안전하게 3D 캐릭터 가이드를 보여줄 수 있다.

    python tools/bake_character.py            # 20프레임, assets/character/sprites/
"""

from __future__ import annotations

import glob
import json
import math
import os
import struct
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHAR_DIR = os.path.join(ROOT, "assets", "character")
OUT_DIR = os.path.join(CHAR_DIR, "sprites")

W, H = 420, 540
FRAMES = 20
YAW_MAX = math.radians(38)  # 좌우 ±38도 왕복


def load_glb(path: str):
    with open(path, "rb") as f:
        magic, ver, total = struct.unpack("<III", f.read(12))
        assert magic == 0x46546C67, "glb 아님"
        clen, ctype = struct.unpack("<II", f.read(8))
        doc = json.loads(f.read(clen))
        blen, btype = struct.unpack("<II", f.read(8))
        buf = f.read(blen)

    def acc_data(idx, ncomp, dtype):
        acc = doc["accessors"][idx]
        bv = doc["bufferViews"][acc["bufferView"]]
        off = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
        n = acc["count"]
        return np.frombuffer(buf[off:off + n * ncomp * dtype().nbytes],
                             dtype=dtype).reshape(n, ncomp).copy()

    prim = doc["meshes"][0]["primitives"][0]
    attrs = prim["attributes"]
    verts = acc_data(attrs["POSITION"], 3, np.float32)
    uvs = acc_data(attrs["TEXCOORD_0"], 2, np.float32) if "TEXCOORD_0" in attrs else None
    iacc = doc["accessors"][prim["indices"]]
    itype = np.uint16 if iacc["componentType"] == 5123 else np.uint32
    tris = acc_data(prim["indices"], 1, itype).reshape(-1, 3).astype(np.int64)

    tex = None
    if doc.get("images"):
        img = doc["images"][0]
        bv = doc["bufferViews"][img["bufferView"]]
        off = bv.get("byteOffset", 0)
        data = np.frombuffer(buf[off:off + bv["byteLength"]], dtype=np.uint8)
        tex = cv2.imdecode(data, cv2.IMREAD_COLOR)  # BGR
    return verts, uvs, tris, tex


def render(verts, uvs, tris, tex, yaw: float) -> np.ndarray:
    """단순 z-버퍼 래스터라이저 (직교 투영, 디퓨즈 + 텍스처)."""
    c, s = math.cos(yaw), math.sin(yaw)
    v = verts.copy()
    x = v[:, 0] * c + v[:, 2] * s
    z = -v[:, 0] * s + v[:, 2] * c
    y = v[:, 1]

    # 화면 맞춤 (회전 불변 스케일)
    rh = float(np.hypot(verts[:, 0], verts[:, 2]).max()) * 2.0
    ylo, yhi = float(verts[:, 1].min()), float(verts[:, 1].max())
    sc = 0.92 * min(W / max(rh, 1e-6), H / max(yhi - ylo, 1e-6))
    px = W / 2 + x * sc
    py = H / 2 - (y - (ylo + yhi) / 2) * sc  # glTF y-up → 이미지 y-down

    rgba = np.zeros((H, W, 4), dtype=np.uint8)
    zbuf = np.full((H, W), -1e9, dtype=np.float32)

    p = np.stack([px, py], axis=1)
    tv = p[tris]                       # (T,3,2)
    tz = z[tris].mean(axis=1)          # 삼각형 깊이(평균)
    # 면 법선 (조명)
    a3 = np.stack([x, y, z], axis=1)[tris]
    n = np.cross(a3[:, 1] - a3[:, 0], a3[:, 2] - a3[:, 0])
    n /= np.maximum(1e-9, np.linalg.norm(n, axis=1))[:, None]
    L = np.array([-0.35, 0.55, 0.76])
    lum = 0.38 + 0.62 * np.clip(np.abs(n @ L), 0, 1)  # 양면 조명

    order = np.argsort(tz)  # 뒤에서 앞으로
    tuv = uvs[tris] if uvs is not None else None
    base_bgr = np.array([160, 231, 127], dtype=np.float64)  # 텍스처 없을 때 민트

    for ti in order:
        (x0, y0), (x1, y1), (x2, y2) = tv[ti]
        minx = max(0, int(min(x0, x1, x2)))
        maxx = min(W - 1, int(max(x0, x1, x2)) + 1)
        miny = max(0, int(min(y0, y1, y2)))
        maxy = min(H - 1, int(max(y0, y1, y2)) + 1)
        if maxx <= minx or maxy <= miny:
            continue
        gx, gy = np.meshgrid(np.arange(minx, maxx + 1), np.arange(miny, maxy + 1))
        d = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(d) < 1e-9:
            continue
        w0 = ((y1 - y2) * (gx - x2) + (x2 - x1) * (gy - y2)) / d
        w1 = ((y2 - y0) * (gx - x2) + (x0 - x2) * (gy - y2)) / d
        w2 = 1.0 - w0 - w1
        inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not inside.any():
            continue
        zt = tz[ti]
        closer = inside & (zt > zbuf[miny:maxy + 1, minx:maxx + 1])
        if not closer.any():
            continue
        if tex is not None and tuv is not None:
            uv = (w0[..., None] * tuv[ti, 0] + w1[..., None] * tuv[ti, 1]
                  + w2[..., None] * tuv[ti, 2])
            tx = np.clip((uv[..., 0] % 1.0) * (tex.shape[1] - 1), 0,
                         tex.shape[1] - 1).astype(np.int32)
            ty = np.clip((uv[..., 1] % 1.0) * (tex.shape[0] - 1), 0,
                         tex.shape[0] - 1).astype(np.int32)
            col = tex[ty, tx].astype(np.float64)
        else:
            col = np.broadcast_to(base_bgr, (*w0.shape, 3)).copy()
        col = np.clip(col * lum[ti], 0, 255).astype(np.uint8)
        region = rgba[miny:maxy + 1, minx:maxx + 1]
        zb = zbuf[miny:maxy + 1, minx:maxx + 1]
        region[..., :3][closer] = col[closer]
        region[..., 3][closer] = 255
        zb[closer] = zt
    return rgba


def main() -> int:
    glbs = sorted(glob.glob(os.path.join(CHAR_DIR, "*.glb")))
    if not glbs:
        print("glb 가 없습니다:", CHAR_DIR)
        return 1
    verts, uvs, tris, tex = load_glb(glbs[0])
    print(f"{os.path.basename(glbs[0])}: 정점 {len(verts):,}, 삼각형 {len(tris):,}, "
          f"텍스처 {'있음' if tex is not None else '없음'}")
    os.makedirs(OUT_DIR, exist_ok=True)
    for i in range(FRAMES):
        # 왕복 턴테이블: -YAW_MAX ~ +YAW_MAX 사인 곡선
        yaw = YAW_MAX * math.sin(2 * math.pi * i / FRAMES)
        img = render(verts, uvs, tris, tex, yaw)
        out = os.path.join(OUT_DIR, f"turn_{i:02d}.png")
        cv2.imwrite(out, img)
        sys.stdout.write(f"\r{i + 1}/{FRAMES} 프레임")
        sys.stdout.flush()
    print(f"\n완료: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
