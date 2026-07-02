"""효과음 + 음성 안내 (데스크톱 앱).

- 효과음: 작은 톤 WAV 를 생성해 QtMultimedia(QSoundEffect)로 재생.
- 음성(TTS): espeak-ng 가 설치돼 있으면 subprocess 로 한국어 발화, 없으면 no-op.
  (설치: sudo apt install espeak-ng)
모두 예외를 삼켜 오디오 불가/헤드리스 환경에서도 앱이 멈추지 않는다.
"""

from __future__ import annotations

import os
import shutil
import struct
import subprocess
import tempfile
import wave

_TONES = {
    "tick": (660.0, 0.10),
    "go": (990.0, 0.20),
    "ok1": (880.0, 0.12),
    "ok2": (1175.0, 0.13),
    "ok3": (1568.0, 0.20),
}


def _gen_wav(path: str, freq: float, dur: float, sr: int = 44100) -> None:
    import math
    n = int(sr * dur)
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        frames = bytearray()
        for i in range(n):
            env = min(1.0, (n - i) / n * 3)  # 페이드아웃
            val = int(0.35 * env * 32767 * math.sin(2 * math.pi * freq * i / sr))
            frames += struct.pack("<h", val)
        w.writeframes(bytes(frames))


class Sound:
    def __init__(self, sound: bool = True, voice: bool = True):
        self.sound = sound
        self.voice = voice and (shutil.which("espeak-ng") is not None)
        self._effects: dict[str, object] = {}
        self._dir = tempfile.mkdtemp(prefix="onlab_snd_")
        self._ok = False
        if not self.sound:
            return
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtMultimedia import QSoundEffect
            for name, (freq, dur) in _TONES.items():
                p = os.path.join(self._dir, f"{name}.wav")
                _gen_wav(p, freq, dur)
                eff = QSoundEffect()
                eff.setSource(QUrl.fromLocalFile(p))
                eff.setVolume(0.5)
                self._effects[name] = eff
            self._ok = True
        except Exception:
            self._ok = False

    def _play(self, name: str) -> None:
        if not (self.sound and self._ok):
            return
        try:
            self._effects[name].play()  # type: ignore[attr-defined]
        except Exception:
            pass

    def tick(self) -> None:
        self._play("tick")

    def go(self) -> None:
        self._play("go")

    def success(self) -> None:
        from PySide6.QtCore import QTimer
        self._play("ok1")
        QTimer.singleShot(120, lambda: self._play("ok2"))
        QTimer.singleShot(250, lambda: self._play("ok3"))

    def fanfare(self) -> None:
        from PySide6.QtCore import QTimer
        for i, name in enumerate(["ok1", "ok2", "ok3"]):
            QTimer.singleShot(i * 160, lambda n=name: self._play(n))

    def speak(self, text: str) -> None:
        if not self.voice:
            return
        try:
            subprocess.Popen(
                ["espeak-ng", "-v", "ko", text],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass
