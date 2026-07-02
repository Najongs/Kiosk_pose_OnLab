/** 카메라 + 포즈추정 컨트롤러 (세션/관리자 캡처가 공유). */

import { PoseEstimatorMP } from "./poseEstimator";
import { PersonPose } from "./keypoints";

export class Camera {
  private stream: MediaStream | null = null;
  private estimator: PoseEstimatorMP | null = null;
  private numPoses = 0;

  constructor(private video: HTMLVideoElement) {}

  async ensure(numPoses = 1): Promise<void> {
    if (!this.stream) {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" },
        audio: false,
      });
      this.video.srcObject = this.stream;
      await this.video.play();
    }
    // numPoses 가 바뀌면 추정기를 재생성 (솔로↔대결 전환)
    if (this.estimator && this.numPoses !== numPoses) {
      this.estimator.close();
      this.estimator = null;
    }
    if (!this.estimator) {
      this.estimator = await PoseEstimatorMP.create(numPoses);
      this.numPoses = numPoses;
    }
  }

  ready(): boolean {
    return this.video.readyState >= 2 && this.video.videoWidth > 0;
  }

  get width(): number {
    return this.video.videoWidth;
  }
  get height(): number {
    return this.video.videoHeight;
  }
  get el(): HTMLVideoElement {
    return this.video;
  }

  estimate(tsMs: number): PersonPose[] {
    if (!this.estimator) return [];
    return this.estimator.estimate(this.video, tsMs);
  }

  stopStream(): void {
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
    this.video.srcObject = null;
  }
}
