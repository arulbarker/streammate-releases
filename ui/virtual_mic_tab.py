# ui/virtual_mic_tab.py

import json
from pathlib import Path

import sounddevice as sd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QComboBox,
    QHBoxLayout, QCheckBox, QPushButton, QGroupBox,
    QFormLayout
)

# ─── fallback untuk list_output_devices ───────────────────────────
try:
    from modules_client.audio_devices import list_output_devices
except ImportError:
    # stub bila tidak ada client module
    def list_output_devices():
        return []

# ─── fallback ConfigManager ───────────────────────────────────────
try:
    from modules_client.config_manager import ConfigManager
except ImportError:
    from modules_server.config_manager import ConfigManager

CONFIG_FILE = "config/live_state.json"
TEMP_DIR    = Path("temp")

class VirtualMicTab(QWidget):
    def __init__(self):
        super().__init__()
        self.cfg = ConfigManager(CONFIG_FILE)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("🎚️ Virtual Microphone"))

        # Load state
        state = {}
        if Path(CONFIG_FILE).exists():
            try:
                state = json.loads(Path(CONFIG_FILE).read_text(encoding="utf-8"))
            except Exception as e:
                print(f"Error loading state: {e}")
                state = {}

        # Daftar output device
        devices = list_output_devices()
        names   = [d["name"] for d in devices]
        if not names:
            layout.addWidget(QLabel("⚠️ Tidak ada perangkat output audio terdeteksi."))
            return

        # Group untuk pengaturan perangkat
        device_group = QGroupBox("Pengaturan Perangkat")
        device_layout = QFormLayout(device_group)

        # Pilihan device
        idx_saved = state.get("virtual_mic_device_index", 0)
        if idx_saved >= len(names):
            idx_saved = 0
            
        self.dev_cb = QComboBox()
        self.dev_cb.addItems(names)
        self.dev_cb.setCurrentIndex(idx_saved)
        device_layout.addRow("Pilih Virtual Mic:", self.dev_cb)
        
        # Toggle aktif
        self.chk_active = QCheckBox("Aktifkan Virtual Mic")
        self.chk_active.setChecked(state.get("virtual_mic_active", False))
        device_layout.addRow("", self.chk_active)
        
        layout.addWidget(device_group)
        
        # Group untuk pengaturan output
        output_group = QGroupBox("Pengaturan Output Suara AI")
        output_layout = QFormLayout(output_group)
        
        # Dual output option
        self.chk_dual = QCheckBox("Dual Output (kirim ke speaker dan virtual mic)")
        self.chk_dual.setChecked(state.get("dual_output", True))
        self.chk_dual.setToolTip("Jika diaktifkan, suara AI akan keluar di speaker PC dan virtual mic")
        output_layout.addRow("", self.chk_dual)
        
        # Volume balancing
        self.chk_volume_boost = QCheckBox("Boost Volume Mic Virtual (+3dB)")
        self.chk_volume_boost.setChecked(state.get("boost_virtual_mic", False))
        self.chk_volume_boost.setToolTip("Meningkatkan volume suara AI di mic virtual")
        output_layout.addRow("", self.chk_volume_boost)
        
        layout.addWidget(output_group)

        # Panduan penggunaan
        help_group = QGroupBox("Panduan Penggunaan")
        help_layout = QVBoxLayout(help_group)
        
        guide = QLabel(
            "📝 <b>Cara Penggunaan Virtual Mic</b>:\n\n"
            "1. <b>Pilih perangkat output</b> yang ingin dijadikan mic virtual (misalnya VB-Cable)\n\n"
            "2. <b>Aktifkan Virtual Mic</b> untuk mengarahkan suara AI ke perangkat tersebut\n\n"
            "3. <b>Untuk Dual Output</b>:\n"
            "   - ON: Suara AI keluar di speaker PC dan mic virtual (cocok untuk monitoring)\n"
            "   - OFF: Suara AI hanya keluar di mic virtual (menghindari echo)\n\n"
            "4. <b>Untuk menghindari suara game tertangkap</b>:\n"
            "   - Gunakan headphone untuk mendengar game\n"
            "   - Atau, nonaktifkan Dual Output saat bermain game dengan speaker\n\n"
            "5. <b>Di OBS/Streamlabs</b>: Pilih perangkat virtual mic sebagai sumber audio"
        )
        guide.setWordWrap(True)
        help_layout.addWidget(guide)
        
        layout.addWidget(help_group)

        # Tombol Simpan dan Test
        buttons_layout = QHBoxLayout()
        
        test_btn = QPushButton("🔊 Test Virtual Mic")
        test_btn.clicked.connect(self._test_virtual_mic)
        buttons_layout.addWidget(test_btn)
        
        save_btn = QPushButton("💾 Simpan Pengaturan")
        save_btn.clicked.connect(self._save_config)
        buttons_layout.addWidget(save_btn)
        
        layout.addLayout(buttons_layout)

        # Status
        self.lbl_status = QLabel()
        self._update_status()
        layout.addWidget(self.lbl_status)

    def _save_config(self):
        """Simpan konfigurasi ke file."""
        try:
            # ambil index & name
            devices = list_output_devices()
            sel_name = self.dev_cb.currentText()
            
            # Cari indeks device berdasarkan nama
            found_device = False
            for d in devices:
                if d["name"] == sel_name:
                    self.cfg.set("virtual_mic_device_index", d["index"])
                    self.cfg.set("virtual_mic_device_name", d["name"])
                    found_device = True
                    break
            
            if not found_device and devices:
                # Fallback ke device pertama jika tidak ditemukan
                self.cfg.set("virtual_mic_device_index", devices[0]["index"])
                self.cfg.set("virtual_mic_device_name", devices[0]["name"])
            
            # Simpan pengaturan lainnya
            self.cfg.set("virtual_mic_active", self.chk_active.isChecked())
            self.cfg.set("dual_output", self.chk_dual.isChecked())
            self.cfg.set("boost_virtual_mic", self.chk_volume_boost.isChecked())

            # simpan ke JSON
            config_data = {
                "virtual_mic_device_index": self.cfg.get("virtual_mic_device_index"),
                "virtual_mic_device_name": self.cfg.get("virtual_mic_device_name"),
                "virtual_mic_active": self.cfg.get("virtual_mic_active"),
                "dual_output": self.cfg.get("dual_output"),
                "boost_virtual_mic": self.cfg.get("boost_virtual_mic")
            }
            
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2)

            self.lbl_status.setText("✅ Pengaturan berhasil disimpan")
            self._update_status()
        except Exception as e:
            self.lbl_status.setText(f"❌ Error: {str(e)}")

    def _update_status(self):
        """Update label status berdasarkan konfigurasi saat ini."""
        status_text = ""
        
        if self.chk_active.isChecked():
            status_text += "🟢 Virtual Mic Aktif"
            
            # Tambahkan info device
            try:
                device_name = self.dev_cb.currentText()
                status_text += f" ({device_name})"
            except:
                pass
            
            # Tambahkan info dual output
            if self.chk_dual.isChecked():
                status_text += " | Mode: Dual Output"
            else:
                status_text += " | Mode: Output Terpisah"
                
            # Tambahkan info volume boost
            if self.chk_volume_boost.isChecked():
                status_text += " | Volume: Boosted"
        else:
            status_text += "🟡 Virtual Mic Nonaktif"
        
        self.lbl_status.setText(status_text)

    def _test_virtual_mic(self):
        """Test virtual mic dengan suara singkat."""
        try:
            # Check if virtual mic is active
            if not self.chk_active.isChecked():
                self.lbl_status.setText("⚠️ Aktifkan Virtual Mic terlebih dahulu")
                return
                
            # Get device index
            device_index = None
            sel_name = self.dev_cb.currentText()
            
            for d in list_output_devices():
                if d["name"] == sel_name:
                    device_index = d["index"]
                    break
            
            if device_index is None:
                self.lbl_status.setText("⚠️ Perangkat tidak ditemukan")
                return
                
            # Import TTS engine for test
            try:
                from modules_server.tts_engine import speak
                
                self.lbl_status.setText("🔊 Memainkan suara test...")
                
                # Run in a separate thread to avoid UI freezing
                import threading
                thread = threading.Thread(
                    target=lambda: speak(
                        "Ini adalah tes virtual microphone. Jika Anda mendengar suara ini di aplikasi streaming, berarti pengaturan berhasil.",
                        language_code="id-ID",
                        output_device=device_index
                    )
                )
                thread.daemon = True
                thread.start()
            except ImportError:
                self.lbl_status.setText("⚠️ TTS Engine tidak tersedia")
        except Exception as e:
            self.lbl_status.setText(f"❌ Test gagal: {str(e)}")