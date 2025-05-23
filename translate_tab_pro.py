from pathlib import Path
import threading, time, keyboard, json
import sounddevice as sd, soundfile as sf
import sys
from pathlib import Path

# Setup path PENTING!
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QComboBox,
    QLineEdit, QPushButton, QHBoxLayout,
    QTextEdit, QCheckBox
)

# ─── ConfigManager ──────────────────────────────────────────────
# ─── fallback modules_client & modules_server ───────────────────────
try:
    from modules_client.config_manager import ConfigManager
    from modules_client.api import generate_reply
    from modules_client.translate_stt import transcribe
    from modules_server.tts_engine import speak
    from modules_server.tts_google import speak_with_google_cloud
    USE_GOOGLE_TTS = True
except ImportError:
    from modules_server.config_manager import ConfigManager
    from modules_server.deepseek_ai import generate_reply
    from modules_server.tts_engine import speak
    # STT hanya ada di client; jika tidak ada, stub error:
    def transcribe(*args, **kwargs):
        raise NotImplementedError("Fitur STT hanya tersedia di environment client")
    USE_GOOGLE_TTS = False

# ─── Translator dynamic ──────────────────────────────────────────
try:
    # client pakai NLBB
    from modules_client.nlbb_translator import translate_dynamic
except ImportError:
    from modules_server.api_translator import translate_dynamic

# ─── TTS speak ───────────────────────────────────────────────────
try:
    from modules_server.tts_engine import speak

except ImportError:
    from modules_server.tts_engine import speak

# ─── STT transcribe ──────────────────────────────────────────────
try:
    from modules_client.translate_stt import transcribe
except ImportError:
    def transcribe(*args, **kwargs):
        raise NotImplementedError("STT hanya tersedia di environment client")

# pastikan folder temp ada
temp_dir = Path("temp")
temp_dir.mkdir(parents=True, exist_ok=True)

class RecorderThread(QThread):
    """Hold-to-talk: record → STT → translate → emit(src, tgt, err)"""
    newTranscript = pyqtSignal(str, str, str)

    def __init__(self, mic_idx: int, src_lang: str):
        super().__init__()
        self.mic_idx  = mic_idx
        self.src_lang = src_lang
        self.buffer   = []
        self.running  = True

    def run(self):
        try:
            with sd.InputStream(
                samplerate=16000, channels=1, device=self.mic_idx,
                callback=lambda indata, *_: self.buffer.extend(indata.copy())
            ):
                while self.running:
                    time.sleep(0.05)
        except Exception as e:
            self.newTranscript.emit("", "", f"Mic error: {e}")
            return

        wav_path = temp_dir / "record.wav"
        try:
            sf.write(str(wav_path), self.buffer, 16000)
            time.sleep(0.1)
        except Exception as e:
            self.newTranscript.emit("", "", f"Gagal simpan rekaman: {e}")
            return

        # STT (pakai Google untuk mode Pro)
        use_google = True
        src = transcribe(str(wav_path), self.src_lang, use_google) or ""
        # filter out Whisper's blank-audio marker
        clean_src = src.replace("[BLANK_AUDIO]", "").strip()
        if not clean_src:
            self.newTranscript.emit("", "", "STT kosong atau gagal")
            return

        # Translate via NLLB
        try:
            tgt = translate_dynamic(clean_src, src_lang=self.src_lang, tgt_lang="eng_Latn") or ""
        except Exception as e:
            self.newTranscript.emit(clean_src, "", f"Translate error: {e}")
            return

        if not tgt.strip():
            self.newTranscript.emit(clean_src, "", "Translate gagal")
        else:
            self.newTranscript.emit(clean_src, tgt, "")


class TranslateTab(QWidget):
    ttsAboutToStart = pyqtSignal()
    ttsFinished     = pyqtSignal()
    def __init__(self):
        super().__init__()
        self.cfg = ConfigManager("config/settings.json")
        self.recorder = None
        self.hotkey_enabled = True

        # load voices
        voices_cfg = json.loads(Path("config/voices.json").read_text(encoding="utf-8"))
        gtts = voices_cfg.get("gtts_standard", {})
        self.voice_map = {
            f"{m['model']} ({lang})": {
                "voice_name": m['model'],
                "language_code": lang
            }
            for lang, ms in gtts.items() for m in ms
        }

        # source-language map
        self.lang_map = {
            "Bahasa Indonesia": "ind_Latn",
            "日本語 (Jepang)":    "jpn_Jpan",
            "中文 (Mandarin)":    "zho_Hans",
            "한국어 (Korea)":     "kor_Hang",
            "العربية (Arab)":    "arb_Arab"
        }

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("🎤 Translate (Hold-to-Talk)"))

        # Mic selector
        row = QHBoxLayout(); row.addWidget(QLabel("Mic:"))
        self.mic = QComboBox()
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0:
                self.mic.addItem(f"{i} | {d['name']}", i)
        idx = self.cfg.get("selected_mic_index", 0)
        self.mic.setCurrentIndex(self.mic.findData(idx))
        row.addWidget(self.mic)
        row.addWidget(self._btn("Test Mic", self.test_mic))
        row.addWidget(self._btn("Save Mic", self.save_mic))
        layout.addLayout(row)

        # Bahasa source
        row = QHBoxLayout(); row.addWidget(QLabel("Bahasa Sumber:"))
        self.lang_combo = QComboBox()
        for lbl in self.lang_map:
            self.lang_combo.addItem(lbl)
        self.lang_combo.setCurrentText("Bahasa Indonesia")
        row.addWidget(self.lang_combo)
        layout.addLayout(row)

        # Voice selector
        row = QHBoxLayout(); row.addWidget(QLabel("Voice:"))
        self.voice_cb = QComboBox()
        for lbl in self.voice_map:
            self.voice_cb.addItem(lbl)
        stored = self.cfg.get("voice_model", "")
        for i, lbl in enumerate(self.voice_map):
            if self.voice_map[lbl]["voice_name"] == stored:
                self.voice_cb.setCurrentIndex(i)
                break
        row.addWidget(self.voice_cb)
        row.addWidget(self._btn("Preview", self.preview_voice))
        row.addWidget(self._btn("Save Voice", self.save_voice))
        layout.addLayout(row)

        # Hotkey Translate
        row = QHBoxLayout(); row.addWidget(QLabel("Hotkey Translate:"))
        self.chk_ctrl  = QCheckBox("Ctrl");  row.addWidget(self.chk_ctrl)
        self.chk_alt   = QCheckBox("Alt");   row.addWidget(self.chk_alt)
        self.chk_shift = QCheckBox("Shift"); row.addWidget(self.chk_shift)
        self.key_combo = QComboBox()
        for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
            self.key_combo.addItem(c)
        row.addWidget(self.key_combo)
        self.hk = QLineEdit(self.cfg.get("translate_hotkey", "Ctrl+Alt+X"))
        self.hk.setReadOnly(True); row.addWidget(self.hk)
        row.addWidget(self._btn("Save", self.save_hotkey))
        self.toggle_btn = QPushButton("🔔 Translate: ON")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setChecked(True)
        self.toggle_btn.clicked.connect(self.toggle_hotkey)
        row.addWidget(self.toggle_btn)
        layout.addLayout(row)

        # Status / Output / Log
        self.status = QLabel("Ready"); layout.addWidget(self.status)
        self.txtbox = QLabel(""); self.txtbox.setWordWrap(True); layout.addWidget(self.txtbox)
        layout.addWidget(QLabel("Log:"))
        self.log = QTextEdit(); self.log.setReadOnly(True); layout.addWidget(self.log)

        # load + start hotkey loop
        self._load_hotkey()
        threading.Thread(target=self._hotkey_loop, daemon=True).start()

    def _btn(self, text, fn):
        b = QPushButton(text); b.clicked.connect(fn); return b

    def _load_hotkey(self):
        th = self.cfg.get("translate_hotkey", "Ctrl+Alt+X")
        for p in th.split("+"):
            if p == "Ctrl":    self.chk_ctrl.setChecked(True)
            elif p == "Alt":   self.chk_alt.setChecked(True)
            elif p == "Shift": self.chk_shift.setChecked(True)
            else:
                i = self.key_combo.findText(p)
                if i >= 0: self.key_combo.setCurrentIndex(i)
        self.hk.setText(th)

    def save_hotkey(self):
        mods = [m for cb,m in [
            (self.chk_ctrl,"Ctrl"),
            (self.chk_alt,"Alt"),
            (self.chk_shift,"Shift")
        ] if cb.isChecked()]
        key = self.key_combo.currentText()
        hot = "+".join(mods + [key]) if key else ""
        self.cfg.set("translate_hotkey", hot)
        self.hk.setText(hot)
        self.log.append(f"[Save] Translate Hotkey → {hot}")

    def toggle_hotkey(self):
        ok = self.toggle_btn.isChecked()
        self.toggle_btn.setText("🔔 Translate: ON" if ok else "🔕 Translate: OFF")
        self.hotkey_enabled = ok

    def test_mic(self):
        duration = 1.0  # durasi rekam dalam detik
        mic_idx  = self.mic.currentData()
        sr       = self.cfg.get("mic_sample_rate", 16000)

        self.log.append(f"[Test Mic] Rekam {duration}s dari mic idx {mic_idx}…")
        try:
            # rekam singkat
            data = sd.rec(int(duration * sr), samplerate=sr,
                          channels=1, device=mic_idx)
            sd.wait()

            self.log.append("[Test Mic] Putar ulang…")
            # play ulang hasil rekaman
            sd.play(data, samplerate=sr)
            sd.wait()

            self.log.append("[Test Mic] Selesai.")
        except Exception as e:
            self.log.append(f"[Test Mic] Error: {e}")


    def save_mic(self):
        self.cfg.set("selected_mic_index", self.mic.currentData())
        self.log.append("[Save] Mic index")

    def preview_voice(self):
        lbl = self.voice_cb.currentText()
        cfg = self.voice_map[lbl]
        self.cfg.set("voice_model", cfg["voice_name"])
        self.log.append(f"[Preview] {lbl}")
        speak("wow arul is very handsome", cfg["language_code"], cfg["voice_name"])  

    def save_voice(self):
        lbl = self.voice_cb.currentText()
        cfg = self.voice_map[lbl]
        self.cfg.set("voice_model", cfg["voice_name"])
        self.log.append("[Save] Voice model")

    def _is_pressed(self, hotkey: str) -> bool:
        return all(keyboard.is_pressed(p.lower()) for p in hotkey.split("+") if p)

    def _hotkey_loop(self):
        prev = False
        while True:
            time.sleep(0.05)
            if not self.hotkey_enabled:
                prev = False
                continue

            hot = self.cfg.get("translate_hotkey", "Ctrl+Alt+X")
            pressed = self._is_pressed(hot)
            if pressed and not prev:
                prev = True
                self.status.setText("🔴 Recording…")
                lang = self.lang_map[self.lang_combo.currentText()]
                self.recorder = RecorderThread(self.mic.currentData(), lang)
                self.recorder.newTranscript.connect(self.on_translate)
                self.recorder.start()
            elif not pressed and prev:
                prev = False
                if self.recorder:
                    self.recorder.running = False
                self.status.setText("⏳ Processing…")

    def on_translate(self, src: str, tgt: str, err: str):
        # kembalikan status UI
        self.status.setText("Ready")

        if err:
            self.txtbox.setText(f"⚠️ {err}")
            self.log.append(f"[Translate] ERROR: {err}")
            return

        # tampilkan hasil
        self.txtbox.setText(f"📝 {src}\n\n🌐 {tgt}")
        self.log.append(f"[Translate] {src} → {tgt}")

        # sinyal: CoHost non-aktif sebelum TTS
        self.ttsAboutToStart.emit()

        def _do_tts(text, lang_code, voice_name):
                try:
                        print(f"[DEBUG] Speak → voice={voice_name}, lang={lang_code}, text={text}")
                        speak(text, lang_code, voice_name)
                except Exception as e:
                        print(f"❌ TTS Error: {e}")
                finally:
                        self.ttsFinished.emit()


        # siapkan parameter suara
        lbl = self.voice_cb.currentText()
        cfg = self.voice_map[lbl]

        # jalankan TTS di thread terpisah
        threading.Thread(
            target=_do_tts,
            args=(tgt, cfg["language_code"], cfg["voice_name"]),
            daemon=True
        ).start()
