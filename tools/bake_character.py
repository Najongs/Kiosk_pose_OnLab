"""리깅 캐릭터(glb)를 스프라이트(RGBA PNG)로 굽는다.

GPU/QtQuick3D 없이 numpy 소프트웨어 래스터라이저(z-버퍼 + 텍스처 +
디퓨즈 셰이딩)로 오프라인 렌더링 → 앱은 이미지를 순환 재생만 하면 되므로
어떤 기기에서도 안전하게 3D 캐릭터 가이드를 보여줄 수 있다.

두 종류를 굽는다:
1. 턴테이블: sprites/turn_XX.png — 좌우로 도는 기본(T포즈) 캐릭터
2. 자세 시연: sprites/<자세이름>/frame_XX.png — 리깅 본을 리타게팅해
   "서있기 → 목표 자세"로 움직이는 시퀀스 (refs3d.json 의 관절 데이터 사용)

    python tools/bake_character.py            # 턴테이블 + 모든 자세 자동
    python tools/bake_character.py --turn-only
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


# ---------- 쿼터니언 유틸 (glTF 순서 [x,y,z,w]) ----------
def q_normalize(q):
    return q / max(1e-12, np.linalg.norm(q))


def q_mul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return np.array([
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    ])


def q_to_mat(q):
    x, y, z, w = q_normalize(q)
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


def mat_to_q(m):
    t = np.trace(m)
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        return q_normalize(np.array([(m[2, 1] - m[1, 2]) / s,
                                     (m[0, 2] - m[2, 0]) / s,
                                     (m[1, 0] - m[0, 1]) / s, 0.25 * s]))
    i = int(np.argmax([m[0, 0], m[1, 1], m[2, 2]]))
    j, k = (i + 1) % 3, (i + 2) % 3
    s = math.sqrt(max(1e-12, 1.0 + m[i, i] - m[j, j] - m[k, k])) * 2
    q = np.zeros(4)
    q[i] = 0.25 * s
    q[j] = (m[j, i] + m[i, j]) / s
    q[k] = (m[k, i] + m[i, k]) / s
    q[3] = (m[k, j] - m[j, k]) / s
    return q_normalize(q)


def q_slerp(a, b, t):
    a = q_normalize(a.astype(np.float64))
    b = q_normalize(b.astype(np.float64))
    d = float(np.dot(a, b))
    if d < 0:
        b, d = -b, -d
    if d > 0.9995:
        return q_normalize(a + t * (b - a))
    th = math.acos(min(1.0, d))
    return q_normalize((math.sin((1 - t) * th) * a + math.sin(t * th) * b)
                       / math.sin(th))


def q_between(u, v):
    """단위벡터 u → v 최단 회전."""
    u = u / max(1e-12, np.linalg.norm(u))
    v = v / max(1e-12, np.linalg.norm(v))
    d = float(np.dot(u, v))
    if d > 0.99999:
        return np.array([0.0, 0.0, 0.0, 1.0])
    if d < -0.99999:  # 정반대 — 수직축 아무거나
        axis = np.cross(u, [1.0, 0.0, 0.0])
        if np.linalg.norm(axis) < 1e-6:
            axis = np.cross(u, [0.0, 1.0, 0.0])
        axis /= np.linalg.norm(axis)
        return np.array([axis[0], axis[1], axis[2], 0.0])
    axis = np.cross(u, v)
    q = np.array([axis[0], axis[1], axis[2], 1.0 + d])
    return q_normalize(q)


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


class Rig:
    """glb 스킨(본 계층 + 웨이트) — 리타게팅과 LBS 스키닝."""

    def __init__(self, path: str):
        with open(path, "rb") as f:
            magic, ver, total = struct.unpack("<III", f.read(12))
            clen, ctype = struct.unpack("<II", f.read(8))
            self.doc = json.loads(f.read(clen))
            blen, btype = struct.unpack("<II", f.read(8))
            self.buf = f.read(blen)
        doc = self.doc

        def acc(idx, ncomp, dtype):
            a = doc["accessors"][idx]
            bv = doc["bufferViews"][a["bufferView"]]
            off = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
            n = a["count"]
            return np.frombuffer(self.buf[off:off + n * ncomp * dtype().nbytes],
                                 dtype=dtype).reshape(n, ncomp).copy()

        prim = doc["meshes"][0]["primitives"][0]
        at = prim["attributes"]
        self.verts = acc(at["POSITION"], 3, np.float32).astype(np.float64)
        self.uvs = acc(at["TEXCOORD_0"], 2, np.float32) if "TEXCOORD_0" in at else None
        self.jidx = acc(at["JOINTS_0"], 4, np.uint16).astype(np.int64)
        self.wts = acc(at["WEIGHTS_0"], 4, np.float32).astype(np.float64)
        iacc = doc["accessors"][prim["indices"]]
        itype = np.uint16 if iacc["componentType"] == 5123 else np.uint32
        self.tris = acc(prim["indices"], 1, itype).reshape(-1, 3).astype(np.int64)

        self.tex = None
        if doc.get("images"):
            bv = doc["bufferViews"][doc["images"][0]["bufferView"]]
            off = bv.get("byteOffset", 0)
            self.tex = cv2.imdecode(
                np.frombuffer(self.buf[off:off + bv["byteLength"]], np.uint8),
                cv2.IMREAD_COLOR)

        skin = doc["skins"][0]
        self.joint_nodes = skin["joints"]
        self.mesh_node = next(i for i, nd in enumerate(doc["nodes"]) if "mesh" in nd)
        self.ibm = acc(skin["inverseBindMatrices"], 16, np.float32) \
            .reshape(-1, 4, 4).transpose(0, 2, 1).astype(np.float64)  # 열우선→행우선

        nodes = doc["nodes"]
        self.n_nodes = len(nodes)
        self.name_to_node = {nd.get("name", ""): i for i, nd in enumerate(nodes)}
        self.parent = [-1] * self.n_nodes
        for i, nd in enumerate(nodes):
            for c in nd.get("children", []):
                self.parent[c] = i
        self.bind_t = np.zeros((self.n_nodes, 3))
        self.bind_q = np.tile(np.array([0.0, 0, 0, 1.0]), (self.n_nodes, 1))
        self.bind_s = np.ones((self.n_nodes, 3))
        for i, nd in enumerate(nodes):
            if "translation" in nd:
                self.bind_t[i] = nd["translation"]
            if "rotation" in nd:
                self.bind_q[i] = nd["rotation"]
            if "scale" in nd:
                self.bind_s[i] = nd["scale"]
        # 계층 순서 (부모 먼저)
        self.order = []
        seen = set()
        def visit(i):
            if i in seen:
                return
            p = self.parent[i]
            if p >= 0 and p not in seen:
                visit(p)
            seen.add(i)
            self.order.append(i)
        for i in range(self.n_nodes):
            visit(i)

    def globals_from(self, quats: np.ndarray) -> np.ndarray:
        """로컬 회전 세트로 전 노드 글로벌 4x4 계산."""
        G = np.tile(np.eye(4), (self.n_nodes, 1, 1))
        for i in self.order:
            L = np.eye(4)
            L[:3, :3] = q_to_mat(quats[i]) * self.bind_s[i][None, :]
            L[:3, 3] = self.bind_t[i]
            p = self.parent[i]
            G[i] = G[p] @ L if p >= 0 else L
        return G

    def skinned(self, quats: np.ndarray) -> np.ndarray:
        """LBS: 로컬 회전 세트 → 변형된 정점 (메시 로컬 공간).
        glTF 스키닝: inv(G_mesh) @ G_joint @ IBM."""
        G = self.globals_from(quats)
        inv_mesh = np.linalg.inv(G[self.mesh_node])
        M = np.einsum("ab,jbc,jcd->jad", inv_mesh,
                      G[self.joint_nodes], self.ibm)  # (J,4,4)
        v4 = np.concatenate([self.verts, np.ones((len(self.verts), 1))], axis=1)
        out = np.zeros((len(self.verts), 3))
        for k in range(4):
            Mk = M[self.jidx[:, k]]                       # (N,4,4)
            out += self.wts[:, k, None] * np.einsum("nab,nb->na", Mk, v4)[:, :3]
        return out


# ---------- MediaPipe 관절 → mixamorig 본 리타게팅 ----------
_MP = {"nose": 0, "ls": 11, "rs": 12, "le": 13, "re": 14, "lw": 15, "rw": 16,
       "lh": 23, "rh": 24, "lk": 25, "rk": 26, "la": 27, "ra": 28}
# (회전시킬 본, 방향 끝점이 되는 자식 본, MP 시작, MP 끝)
_AIMS = [
    ("mixamorig:Spine", "mixamorig:Neck", "hip_mid", "sh_mid"),
    ("mixamorig:Neck", "mixamorig:Head", "sh_mid", "nose"),
    ("mixamorig:LeftArm", "mixamorig:LeftForeArm", "ls", "le"),
    ("mixamorig:LeftForeArm", "mixamorig:LeftHand", "le", "lw"),
    ("mixamorig:RightArm", "mixamorig:RightForeArm", "rs", "re"),
    ("mixamorig:RightForeArm", "mixamorig:RightHand", "re", "rw"),
    ("mixamorig:LeftUpLeg", "mixamorig:LeftLeg", "lh", "lk"),
    ("mixamorig:LeftLeg", "mixamorig:LeftFoot", "lk", "la"),
    ("mixamorig:RightUpLeg", "mixamorig:RightLeg", "rh", "rk"),
    ("mixamorig:RightLeg", "mixamorig:RightFoot", "rk", "ra"),
]
_MIN_VIS = 0.3


def _mp_points(ref3d) -> dict[str, np.ndarray] | None:
    """MP 월드(x우, y하, z) → glTF(y상) 좌표계 점들. 부족하면 None."""
    def pt(i):
        if i < len(ref3d) and len(ref3d[i]) >= 4 and ref3d[i][3] >= _MIN_VIS:
            x, y, z = ref3d[i][0], ref3d[i][1], ref3d[i][2]
            return np.array([x, -y, -z])
        return None
    pts = {k: pt(i) for k, i in _MP.items()}
    if pts["ls"] is None or pts["rs"] is None or pts["lh"] is None or pts["rh"] is None:
        return None
    pts["sh_mid"] = (pts["ls"] + pts["rs"]) / 2
    pts["hip_mid"] = (pts["lh"] + pts["rh"]) / 2
    return pts


def retarget(rig: Rig, ref3d) -> np.ndarray | None:
    """자세의 최종 로컬 회전 세트 (bind 에서 필요한 본만 회전)."""
    pts = _mp_points(ref3d)
    if pts is None:
        return None
    quats = rig.bind_q.copy()
    for bone, tip, mp_a, mp_b in _AIMS:
        if bone not in rig.name_to_node or tip not in rig.name_to_node:
            continue
        a, b = pts.get(mp_a), pts.get(mp_b)
        if a is None or b is None:
            continue
        nb = rig.name_to_node[bone]
        nt = rig.name_to_node[tip]
        G = rig.globals_from(quats)
        cur = G[nt][:3, 3] - G[nb][:3, 3]
        if np.linalg.norm(cur) < 1e-9:
            continue
        dq = q_between(cur, b - a)
        R_new = q_to_mat(dq) @ G[nb][:3, :3]
        p = rig.parent[nb]
        Rp = G[p][:3, :3] if p >= 0 else np.eye(3)
        # 스케일 제거 후 로컬 회전 추출
        Rp_n = Rp / np.maximum(1e-12, np.linalg.norm(Rp, axis=0, keepdims=True))
        R_new_n = R_new / np.maximum(1e-12, np.linalg.norm(R_new, axis=0, keepdims=True))
        quats[nb] = mat_to_q(Rp_n.T @ R_new_n)
    return quats


def render(verts, uvs, tris, tex, yaw: float, bounds=None) -> np.ndarray:
    """단순 z-버퍼 래스터라이저 (직교 투영, 디퓨즈 + 텍스처).
    bounds=(rh, ylo, yhi) 를 주면 프레임 간 화면 맞춤 고정(애니메이션용)."""
    c, s = math.cos(yaw), math.sin(yaw)
    v = verts.copy()
    x = v[:, 0] * c + v[:, 2] * s
    z = -v[:, 0] * s + v[:, 2] * c
    y = v[:, 1]

    # 화면 맞춤 (회전 불변 스케일)
    if bounds is not None:
        rh, ylo, yhi = bounds
    else:
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


POSE_FRAMES = 12
POSE_YAW = 0.30  # 자세 시연 시 고정 요(살짝 비스듬히 → 깊이 보임)


def bake_pose(rig: Rig, slug: str, ref3d, frames: int = POSE_FRAMES) -> bool:
    """서있기 → 목표 자세 진행 시퀀스를 sprites/<slug>/ 에 굽는다."""
    q_final = retarget(rig, ref3d)
    if q_final is None:
        print(f"  [건너뜀] {slug}: 관절 데이터 부족")
        return False
    v_final = rig.skinned(q_final)
    both = np.vstack([rig.verts, v_final])
    bounds = (float(np.hypot(both[:, 0], both[:, 2]).max()) * 2.0,
              float(both[:, 1].min()), float(both[:, 1].max()))
    outdir = os.path.join(OUT_DIR, slug)
    os.makedirs(outdir, exist_ok=True)
    for i in range(frames):
        u = i / (frames - 1)
        u = u * u * (3 - 2 * u)  # smoothstep
        qs = np.array([q_slerp(rig.bind_q[n], q_final[n], u)
                       for n in range(rig.n_nodes)])
        v = rig.skinned(qs)
        img = render(v, rig.uvs, rig.tris, rig.tex, POSE_YAW, bounds)
        cv2.imwrite(os.path.join(outdir, f"frame_{i:02d}.png"), img)
        sys.stdout.write(f"\r  {slug}: {i + 1}/{frames}")
        sys.stdout.flush()
    print()
    return True


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--turn-only", action="store_true", help="턴테이블만 굽기")
    ap.add_argument("--pose", default=None, help="특정 자세만 굽기")
    args = ap.parse_args()

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
        cv2.imwrite(os.path.join(OUT_DIR, f"turn_{i:02d}.png"), img)
        sys.stdout.write(f"\r턴테이블 {i + 1}/{FRAMES}")
        sys.stdout.flush()
    print()
    if args.turn_only:
        print(f"완료: {OUT_DIR}")
        return 0

    # 자세 시연 굽기 (refs3d.json 의 관절 데이터 → 리깅 리타게팅)
    refs_path = os.path.join(ROOT, "config", "refs3d.json")
    try:
        with open(refs_path, encoding="utf-8") as f:
            refs3d = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        refs3d = {}
    if not refs3d:
        print("refs3d.json 이 없어 자세 시퀀스는 생략 —")
        print("  MediaPipe 되는 PC 에서 `python tools/import_poses.py` 후 다시 실행하세요.")
        return 0
    rig = Rig(glbs[0])
    targets = {args.pose: refs3d[args.pose]} if args.pose else refs3d
    made = 0
    for slug, ref in targets.items():
        made += bake_pose(rig, slug, ref)
    print(f"완료: 자세 {made}개 → {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
