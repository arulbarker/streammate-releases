from pathlib import Path
import threading, time, keyboard, json
import sounddevice as sd, soundfile as sf
from datetime import datetime 
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QComboBox,
    QLineEdit, QPushButton, QHBoxLayout,
    QTextEdit, QCheckBox, QMessageBox  # Tambahkan QMessageBox di sini
)
from modules_client.subscription_checker import register_activity

# ─── ConfigManager ──────────────────────────────────────────────
try:
    from modules_client.config_manager import ConfigManager
except ImportError:
    from modules_server.config_manager import ConfigManager

# ─── Translator dynamic ──────────────────────────────────────────
# lokal: pakai NLLB, production: pakai API server
try:
    from modules_client.nlbb_translator import translate_dynamic
except ImportError:
    from modules_server.api_translator import translate_dynamic

# ─── TTS speak ───────────────────────────────────────────────────
try:
    from modules_server.tts_engine import speakcl

except ImportError:
    from modules_server.tts_engine import speak

# ─── STT Whisper ─────────────────────────────────────────────────
try:
    from modules_client.translate_stt import _whisper_transcribe
except ImportError:
    def _whisper_transcribe(*args, **kwargs):
        raise NotImplementedError("STT hanya tersedia di lingkungan pengembangan lokal")

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
        # record until .running=False
        # Periksa status demo jika ada
        subscription_file = Path("config/subscription_status.json")
        is_demo = False
        if subscription_file.exists():
            try:
                data = json.loads(subscription_file.read_text(encoding="utf-8"))
                if data.get("status") == "demo":
                    is_demo = True
                    expire_date = datetime.fromisoformat(data.get("expire_date", "2000-01-01"))
                    if expire_date <= datetime.now():
                        # Demo sudah expired
                        QMessageBox.warning(
                            self,
                            "Demo Expired",
                            "Waktu demo 30 menit telah berakhir.\n"
                            "Silakan beli kredit untuk melanjutkan.",
                        )
                        return
                    # Demo masih valid, lanjutkan tanpa cek kredit lain
            except Exception as e:
                print(f"[DEBUG] Error reading demo status: {e}")
                is_demo = False
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

        # Check if we have audio data
        if not self.buffer:
            self.newTranscript.emit("", "", "Tidak ada audio terekam")
            return

        # Normalize and save wav
        wav_path = temp_dir / "record.wav"
        try:
            import numpy as np
            audio_data = np.array(self.buffer)

            # Normalize untuk memastikan volume cukup
            if np.max(np.abs(audio_data)) > 0:
                audio_data = audio_data / np.max(np.abs(audio_data))

            sf.write(str(wav_path), audio_data, 16000)
            time.sleep(0.1)
        except Exception as e:
            self.newTranscript.emit("", "", f"Gagal simpan rekaman: {e}")
            return

        # STT Whisper
        src = _whisper_transcribe(str(wav_path)) or ""
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
    ttsFinished = pyqtSignal()
    ttsAboutToStart = pyqtSignal()
    ttsFinished     = pyqtSignal()
    def __init__(self):
        super().__init__()
        self.cfg = ConfigManager("config/settings.json")
        self.recorder = None
        self.hotkey_enabled = True

        # dua pilihan suara Standard (Google Cloud Standard voices)
        # kita ambil en-US-Standard-A (MALE) dan en-US-Standard-C (FEMALE)
        self.voice_options = {}
        try:
            voices_data = json.loads(Path("config/voices.json").read_text(encoding="utf-8")).get("gtts_standard", {})
            
            # Isi untuk suara English
            en_voices = voices_data.get("en-US", [])
            
            # Tambahkan semua suara English ke voice_options
            for voice in en_voices:
                gender = voice.get("gender", "").upper()
                model_id = voice.get("model", "")
                if gender and model_id:
                    # Format label: "Gender - Model Name"
                    label = f"{gender} - {model_id}"
                    self.voice_options[label] = {
                        "voice_name": model_id,
                        "language_code": "en-US"
                    }
        except Exception as e:
            # Fallback jika gagal memuat dari voices.json
            self.voice_options = {
                "MALE - en-US-Standard-B": {"voice_name": "en-US-Standard-B", "language_code": "en-US"},
                "FEMALE - en-US-Standard-C": {"voice_name": "en-US-Standard-C", "language_code": "en-US"}
            }

        # source-language map tetap
        self.lang_map = {
            "Bahasa Indonesia": "ind_Latn",
            "日本語 (Jepang)":    "jpn_Jpan",
            "中文 (Mandarin)":    "zho_Hans",
            "한국어 (Korea)":     "kor_Hang",
            "العربية (Arab)":    "arb_Arab"
        }

        # ─── UI ────────────────────────────────────────────────────────
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

        # Voice selector (hanya Male & Female)
        row = QHBoxLayout(); row.addWidget(QLabel("Voice:"))
        # Isi dropdown suara dengan semua opsi
        self.voice_cb = QComboBox()
        for label in sorted(self.voice_options.keys()):
            self.voice_cb.addItem(label, label)
        # restore pilihan dari config
        stored = self.cfg.get("translate_voice", "MALE - en-US-Standard-B")
        idx = self.voice_cb.findData(stored)
        if idx >= 0:
            self.voice_cb.setCurrentIndex(idx)
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

        # ─── Init hotkey loop ─────────────────────────────────────────
        self._load_hotkey()
        threading.Thread(target=self._hotkey_loop, daemon=True).start()

    def _btn(self, text, fn):
        b = QPushButton(text); b.clicked.connect(fn); return b

    # ─── Mic helpers ───────────────────────────────────────────────
    def test_mic(self):
        duration = 1.0  # durasi rekam dalam detik
        mic_idx  = self.mic.currentData()
        sr       = 16000  # Fixed sample rate untuk compatibility

        self.log.append(f"[Test Mic] Rekam {duration}s dari mic idx {mic_idx}…")
        try:
            # Record audio
            data = sd.rec(int(duration * sr), samplerate=sr,
                          channels=1, device=mic_idx)
            sd.wait()

            # Normalize audio untuk memastikan volume cukup
            import numpy as np
            data = data / np.max(np.abs(data))

            self.log.append("[Test Mic] Putar ulang…")
            # Gunakan sample rate yang sama untuk playback
            sd.play(data, samplerate=sr)
            sd.wait()
            self.log.append("[Test Mic] Selesai.")
        except Exception as e:
            self.log.append(f"[Test Mic] Error: {e}")

    def save_mic(self):
        # simpan mic index ke config, dipakai reload next time
        self.cfg.set("selected_mic_index", self.mic.currentData())
        self.log.append("[Save] Mic index")



    # ─── Voice helpers ────────────────────────────────────────────
    def preview_voice(self):
        label = self.voice_cb.currentData()
        opt = self.voice_options[label]
        voice_name = opt["voice_name"]
        lang_code = opt["language_code"]
    
        self.log.append(f"[Preview] Label: {label}, Voice: {voice_name}, Lang: {lang_code}")
    
        # Tambahkan delay sejenak sebelum memanggil TTS
        self.status.setText("Memuat preview suara...")
    
        # Gunakan QTimer untuk menghindari UI freeze
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, lambda: self._do_preview_voice(voice_name, lang_code))

    def _do_preview_voice(self, voice_name, lang_code):
        try:
            speak("wow arul is very handsome and kind", lang_code, voice_name)
            self.status.setText("Preview selesai")
        except Exception as e:
            self.log.append(f"[ERROR] Preview voice failed: {str(e)}")
            self.status.setText("Preview gagal")

    def save_voice(self):
        label = self.voice_cb.currentData()
        self.cfg.set("translate_voice", label)
        self.log.append(f"[Save] Voice → {label}")

    # ─── Hotkey helpers ───────────────────────────────────────────
    def _load_hotkey(self):
        th = self.cfg.get("translate_hotkey", "Ctrl+Alt+X")
        for p in th.split("+"):
            if p=="Ctrl":    self.chk_ctrl.setChecked(True)
            elif p=="Alt":   self.chk_alt.setChecked(True)
            elif p=="Shift": self.chk_shift.setChecked(True)
            else:
                i = self.key_combo.findText(p)
                if i>=0: self.key_combo.setCurrentIndex(i)
        self.hk.setText(th)

    def save_hotkey(self):
        mods = [m for cb,m in [
            (self.chk_ctrl,"Ctrl"),
            (self.chk_alt,"Alt"),
            (self.chk_shift,"Shift")
        ] if cb.isChecked()]
        key = self.key_combo.currentText()
        hot = "+".join(mods + ([key] if key else []))
        self.cfg.set("translate_hotkey", hot)
        self.hk.setText(hot)
        self.log.append(f"[Save] Translate Hotkey → {hot}")

    def toggle_hotkey(self):
        ok = self.toggle_btn.isChecked()
        self.toggle_btn.setText("🔔 Translate: ON" if ok else "🔕 Translate: OFF")
        self.hotkey_enabled = ok

    # ─── Hotkey loop ──────────────────────────────────────────────
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
                register_activity("translate_basic")
            elif not pressed and prev:
                prev = False
                if self.recorder:
                    self.recorder.running = False
                self.status.setText("⏳ Processing…")

     # ─── Handle hasil translate + TTS gTTS full ────────────────────
    # ─── Handle hasil translate + TTS gTTS full ────────────────────
    def on_translate(self, src: str, tgt: str, err: str):
        self.status.setText("Ready")
        if err:
            self.txtbox.setText(f"⚠️ {err}")
            self.log.append(f"[Translate] Gagal: {err}")
            return

        self.txtbox.setText(f"📝 {src}\n\n🌐 {tgt}")
        self.log.append(f"[Translate] {src} → {tgt}")

        # mute CoHost sebelum TTS
        self.ttsAboutToStart.emit()

        def _do_tts(text, lang_code, voice_name):
                try:
                        print(f"[DEBUG] Speak → voice={voice_name}, lang={lang_code}, text={text}")
                        speak(text, lang_code, voice_name)
                except Exception as e:
                        print(f"❌ TTS Error: {e}")
                finally:
                        self.ttsFinished.emit()

        # register activity ke server
        register_activity("translate_basic")


        cfg = self.voice_options[self.voice_cb.currentData()]
        threading.Thread(
            target=_do_tts,
            args=(tgt, cfg["language_code"], cfg["voice_name"]),
            daemon=True
        ).start()


