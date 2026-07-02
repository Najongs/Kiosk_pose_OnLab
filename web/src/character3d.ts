/** 3D 캐릭터 가이드 — 리깅된 glTF(public/character.glb)를 가이드 박스
 * 위치의 WebGL 오버레이 캔버스에 로드해 내장 애니메이션을 재생하고
 * 천천히 턴테이블 회전시킨다. 파일이 없으면 조용히 비활성(2D 썸네일 유지).
 *
 * 1단계(현재): 캐릭터 + 내장 애니메이션 재생 (파이프라인 검증)
 * 2단계(예정): 목표 자세 관절 데이터로 본 리타게팅
 */

import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

export class CharacterGuide {
  ready = false;
  private el: HTMLCanvasElement;
  private renderer: THREE.WebGLRenderer | null = null;
  private scene = new THREE.Scene();
  private camera: THREE.PerspectiveCamera | null = null;
  private mixer: THREE.AnimationMixer | null = null;
  private root: THREE.Object3D | null = null;
  private clock = new THREE.Clock();
  private raf = 0;
  private visible = false;

  constructor(canvas: HTMLCanvasElement) {
    this.el = canvas;
  }

  async load(url = "character.glb"): Promise<boolean> {
    try {
      const head = await fetch(url, { method: "HEAD" });
      if (!head.ok) return false;
      this.renderer = new THREE.WebGLRenderer({
        canvas: this.el, alpha: true, antialias: true,
      });
      this.renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
      this.scene.add(new THREE.HemisphereLight(0xeef2fb, 0x223, 1.1));
      const key = new THREE.DirectionalLight(0xffffff, 1.6);
      key.position.set(-2, 3, 4);
      this.scene.add(key);

      const gltf = await new GLTFLoader().loadAsync(url);
      this.root = gltf.scene;
      // 모델을 원점 중앙·단위 높이로 정규화
      const box = new THREE.Box3().setFromObject(this.root);
      const size = box.getSize(new THREE.Vector3());
      const center = box.getCenter(new THREE.Vector3());
      const s = 1.7 / Math.max(size.y, 1e-6);
      this.root.scale.setScalar(s);
      this.root.position.sub(center.multiplyScalar(s));
      const holder = new THREE.Group();
      holder.add(this.root);
      this.scene.add(holder);
      this.root = holder;

      this.camera = new THREE.PerspectiveCamera(35, 0.8, 0.1, 20);
      this.camera.position.set(0, 0.25, 3.4);
      this.camera.lookAt(0, 0, 0);

      if (gltf.animations.length) {
        this.mixer = new THREE.AnimationMixer(gltf.scene);
        this.mixer.clipAction(gltf.animations[0]).play();
      }
      this.ready = true;
      return true;
    } catch (e) {
      console.warn("3D 캐릭터 로드 실패(2D 썸네일 사용):", e);
      return false;
    }
  }

  setVisible(v: boolean): void {
    if (!this.ready || v === this.visible) {
      if (!this.ready) this.el.style.display = "none";
      return;
    }
    this.visible = v;
    this.el.style.display = v ? "block" : "none";
    if (v) {
      this.clock.getDelta(); // 큰 dt 점프 방지
      this.loop();
    } else {
      cancelAnimationFrame(this.raf);
    }
  }

  private loop = (): void => {
    if (!this.visible || !this.renderer || !this.camera) return;
    const w = this.el.clientWidth;
    const h = this.el.clientHeight;
    if (w > 0 && h > 0 &&
        (this.el.width !== w * this.renderer.getPixelRatio() ||
         this.el.height !== h * this.renderer.getPixelRatio())) {
      this.renderer.setSize(w, h, false);
      this.camera.aspect = w / h;
      this.camera.updateProjectionMatrix();
    }
    const dt = this.clock.getDelta();
    this.mixer?.update(dt);
    if (this.root) {
      this.root.rotation.y = 0.5 * Math.sin(performance.now() / 1600); // 턴테이블
    }
    this.renderer.render(this.scene, this.camera);
    this.raf = requestAnimationFrame(this.loop);
  };
}
