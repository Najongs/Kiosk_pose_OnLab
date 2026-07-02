"""배경음악(BGM) — assets/bgm/ 폴더의 음악 파일을 반복 재생.

파일이 하나면 무한 루프, 여러 개면 순서대로 돌아가며 재생한다.
폴더가 비어 있으면 조용히 아무것도 하지 않는다(에러 없음).

음원 넣는 법: 저작권 무료 음원(예: pixabay.com/music, incompetech.com)을
받아 assets/bgm/ 에 mp3/wav/ogg 로 넣으면 앱 시작 시 자동 재생된다.
관리자 화면의 '배경음악' 체크로 켜고 끌 수 있다.
"""

from __future__ import annotations

import os

_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "bgm")
_EXTS = (".mp3", ".wav", ".ogg", ".m4a", ".flac")


class Bgm:
    def __init__(self, volume: float = 0.25):
        self._files: list[str] = []
        self._idx = 0
        self._player = None
        self._out = None
        self._volume = volume
        try:
            if os.path.isdir(_DIR):
                self._files = sorted(
                    os.path.join(_DIR, f) for f in os.listdir(_DIR)
                    if f.lower().endswith(_EXTS))
        except OSError:
            pass

    @property
    def available(self) -> bool:
        return bool(self._files)

    def start(self) -> None:
        if not self._files or self._player is not None:
            return
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
            self._out = QAudioOutput()
            self._out.setVolume(self._volume)
            self._player = QMediaPlayer()
            self._player.setAudioOutput(self._out)
            if len(self._files) == 1:
                self._player.setLoops(QMediaPlayer.Loops.Infinite)
            else:
                self._player.mediaStatusChanged.connect(self._on_status)
            self._player.setSource(QUrl.fromLocalFile(self._files[self._idx]))
            self._player.play()
        except Exception:
            # 오디오 장치 없음/코덱 미지원 등 — BGM 없이 계속
            self._player = None
            self._out = None

    def _on_status(self, status) -> None:
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtMultimedia import QMediaPlayer
            if status == QMediaPlayer.MediaStatus.EndOfMedia and self._player is not None:
                self._idx = (self._idx + 1) % len(self._files)
                self._player.setSource(QUrl.fromLocalFile(self._files[self._idx]))
                self._player.play()
        except Exception:
            pass

    def stop(self) -> None:
        if self._player is not None:
            try:
                self._player.stop()
            except Exception:
                pass
        self._player = None
        self._out = None
