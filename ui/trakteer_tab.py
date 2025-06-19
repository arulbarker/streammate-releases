# ui/trakteer_tab.py
import time, threading, requests, os
from PyQt6.QtCore    import QThread, pyqtSignal, QTimer, Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QCheckBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QSizePolicy, QMessageBox
)

# Selalu pakai modul "server" (lebih lengkap & stabil)
from modules_server.config_manager import ConfigManager
from modules_server.deepseek_ai    import generate_reply
from modules_server.tts_engine     import speak     # <= pastikan voice engine sama di semua mesin

# Import modul tambahan untuk mendapatkan API bridge yang sama dengan cohost_tab
from modules_client.api import generate_reply as client_generate_reply

# --- Helper Class for API Calls ---
class TrakteerAPI:
    """Wrapper untuk panggilan Trakteer API."""
    BASE_URL = "https://api.trakteer.id/v1/public"

    def __init__(self, api_key):
        self.api_key = api_key.strip()
        self.headers = {
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "key": self.api_key
        }

    def _request(self, method, endpoint, params=None, json_data=None):
        url = f"{self.BASE_URL}/{endpoint}"
        try:
            print(f"[DEBUG] API Request: {method} {url} params={params}")
            if method.upper() == "POST" and json_data:
                r = requests.post(url, headers=self.headers, json=json_data, timeout=10)
            else:
                r = requests.request(method, url, headers=self.headers, params=params, timeout=10)
                
            print(f"[DEBUG] API Response status: {r.status_code}")
            if r.status_code == 422:
                print(f"[DEBUG] API 422 Response: {r.text}")
                # Tangani error 422 secara khusus (parameter tidak valid)
                return {"status": "error", "message": f"Parameter tidak valid: {r.text[:100]}"}
            r.raise_for_status()  # Raise exception for other bad status codes
            
            response_json = r.json()
            print(f"[DEBUG] API Response: {response_json.get('status')}")
            return response_json
        except requests.exceptions.RequestException as e:
            print(f"❌ Trakteer API error on {endpoint}: {e}")
            return {"status": "error", "message": str(e)}
        except Exception as e:
            print(f"❌ Unexpected error on {endpoint}: {e}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    def get_supports(self, **kwargs):
        # Mengambil riwayat dukungan dengan parameter yang benar sesuai dokumentasi
        params = {}
        if kwargs.get("limit"):
            params["limit"] = kwargs.get("limit")
        if kwargs.get("page"):
            params["page"] = kwargs.get("page")
        
        # Tambahkan include sesuai dokumentasi API
        includes = []
        
        # Selalu sertakan informasi penting
        includes.append("supporter_email")  # Untuk mendapatkan email supporter jika diizinkan
        
        if kwargs.get("include_order_id"):
            includes.append("order_id")
        if kwargs.get("include_payment"):
            includes.append("payment_method")
            
        if includes:
            params["include"] = ",".join(includes)
            
        return self._request("GET", "supports", params=params)

    def get_current_balance(self):
        return self._request("GET", "current-balance")

    def get_quantity_given(self, email):
        """Mendapatkan jumlah unit trakteer-an yang telah diberikan oleh supporter."""
        try:
            data = {"email": email}
            return self._request("POST", "quantity-given", json_data=data)
        except Exception as e:
            print(f"❌ Trakteer API error on quantity-given: {e}")
            return {"status": "error", "message": str(e)}

# --- Polling Thread for Live Donations ---
class TrakteerPollingThread(QThread):
    """Thread untuk polling donasi baru secara berkala."""
    new_support_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, api_key, interval=5):
        super().__init__()
        self.api = TrakteerAPI(api_key)
        self.interval = interval
        self._is_running = True
        self.consecutive_errors = 0
        self.max_consecutive_errors = 5

    def run(self):
        print(f"[INFO] Trakteer polling started. Key: {self.api.api_key[:5]}...")
        while self._is_running:
            try:
                # Gunakan parameter minimal yang dibutuhkan untuk menghindari error 422
                # Tambahkan supporter_email untuk mendapatkan informasi pendonasi
                response = self.api.get_supports(limit=1, page=1, include_order_id=True)
                
                if response and response.get("status") == "success":
                    data = response.get("result", {}).get("data", [])
                    if data:
                        self.consecutive_errors = 0  # Reset error counter
                        self.new_support_signal.emit(data[0])
                elif response:
                    self.error_signal.emit(f"API Error: {response.get('message', 'Unknown error')}")
                    self.consecutive_errors += 1
                else:
                    self.error_signal.emit("API Error: No response from server.")
                    self.consecutive_errors += 1
                
                # Jika terlalu banyak error berturut-turut, kurangi frekuensi polling
                if self.consecutive_errors > self.max_consecutive_errors:
                    self.error_signal.emit(f"Too many consecutive errors. Reducing polling frequency.")
                    time.sleep(30)  # Tunggu lebih lama
                    self.consecutive_errors = 0  # Reset counter
            except Exception as e:
                self.error_signal.emit(f"Polling error: {str(e)}")
                self.consecutive_errors += 1
            
            # Tunggu interval sebelum polling berikutnya
            for _ in range(self.interval):
                if not self._is_running:
                    break
                time.sleep(1)

    def stop(self):
        self._is_running = False
        self.wait()
        print("[INFO] Trakteer polling stopped.")

# ──────────────────────────────────────────────────────
class TrakteerTab(QWidget):
    muteRequested = pyqtSignal()
    muteReleased  = pyqtSignal()
    # Tambahkan signal baru untuk update log
    logUpdated = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.cfg           = ConfigManager("config/settings.json")
        self.polling_thread = None
        self.last_order_id = None
        self.api = None
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # 1. Bagian API Key
        api_layout = QHBoxLayout()
        api_layout.addWidget(QLabel("Trakteer API Key:"))
        self.key_input = QLineEdit(self.cfg.get("tr_api_key", ""))
        self.key_input.setPlaceholderText("Masukkan API Key Anda di sini")
        api_layout.addWidget(self.key_input)
        
        self.save_key_btn = QPushButton("💾 Simpan & Inisialisasi")
        self.save_key_btn.clicked.connect(self.save_and_init_api)
        api_layout.addWidget(self.save_key_btn)
        main_layout.addLayout(api_layout)

        # 2. Bagian Saldo
        balance_layout = QHBoxLayout()
        self.balance_label = QLabel("Saldo: Rp -")
        self.balance_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        balance_layout.addWidget(self.balance_label)
        
        self.refresh_balance_btn = QPushButton("🔄 Refresh Saldo")
        self.refresh_balance_btn.clicked.connect(self.refresh_balance)
        self.refresh_balance_btn.setEnabled(False) # Diaktifkan setelah API key valid
        balance_layout.addWidget(self.refresh_balance_btn)
        main_layout.addLayout(balance_layout)

        # 3. Tab Widget
        self.tabs = QTabWidget()
        self._create_live_donations_tab()
        self._create_support_history_tab()
        main_layout.addWidget(self.tabs)
        
        # Inisialisasi API jika key sudah ada
        if self.cfg.get("tr_api_key"):
            try:
                self.save_and_init_api()
            except Exception as e:
                print(f"Error initializing API: {e}")
                # Jangan crash jika inisialisasi gagal

    def _create_live_donations_tab(self):
        live_tab = QWidget()
        layout = QVBoxLayout(live_tab)

        self.listener_checkbox = QCheckBox("Aktifkan Listener Donasi Real-time")
        self.listener_checkbox.toggled.connect(self._toggle_listener)
        self.listener_checkbox.setEnabled(False) # Diaktifkan setelah API key valid
        layout.addWidget(self.listener_checkbox)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("Log donasi dan balasan AI akan muncul di sini...")
        layout.addWidget(self.log_view)

        # Tambahkan tombol test AI
        test_btn = QPushButton("🧪 Test AI Response")
        test_btn.clicked.connect(self._test_ai_response)
        layout.addWidget(test_btn)

        self.tabs.addTab(live_tab, "📢 Donasi Live")
    
    def _create_support_history_tab(self):
        history_tab = QWidget()
        layout = QVBoxLayout(history_tab)

        self.refresh_history_btn = QPushButton("🔄 Muat Ulang Riwayat")
        self.refresh_history_btn.clicked.connect(self.refresh_support_history)
        self.refresh_history_btn.setEnabled(False)
        layout.addWidget(self.refresh_history_btn)
        
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels(["Waktu", "Donatur", "Jumlah", "Unit", "Pesan"])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.history_table)
        
        self.tabs.addTab(history_tab, "📖 Riwayat Dukungan")

    # --- UI Logic & Event Handlers ---
    def _log(self, message):
        """Menambahkan pesan ke log view di thread-safe."""
        try:
            self.log_view.append(message)
            self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())
            print(message)
        except Exception as e:
            print(f"Error logging message: {e}")

    def _test_ai_response(self):
        """Fungsi untuk menguji respons AI"""
        self._log("[TEST] Menguji koneksi AI...")
        
        test_prompt = "Ini adalah test koneksi ke AI. Tolong berikan respons singkat untuk memastikan koneksi berfungsi."
        
        # Jalankan di thread terpisah untuk tidak memblokir UI
        threading.Thread(target=self._test_ai_worker, args=(test_prompt,), daemon=True).start()
    
    def _test_ai_worker(self, prompt):
        """Worker untuk menguji respons AI"""
        try:
            # Coba metode 1: Menggunakan client_generate_reply (dari modules_client.api)
            self._log("[TEST] Mencoba metode 1: client_generate_reply...")
            reply = client_generate_reply(prompt)
            
            if reply and len(reply) > 10:
                self._log(f"[TEST] ✅ Metode 1 berhasil: {reply[:50]}...")
                return
            else:
                self._log("[TEST] ❌ Metode 1 gagal: tidak ada respons atau terlalu pendek")
            
            # Coba metode 2: Menggunakan generate_reply langsung (dari modules_server.deepseek_ai)
            self._log("[TEST] Mencoba metode 2: generate_reply langsung...")
            reply = generate_reply(prompt)
            
            if reply and len(reply) > 10:
                self._log(f"[TEST] ✅ Metode 2 berhasil: {reply[:50]}...")
                return
            else:
                self._log("[TEST] ❌ Metode 2 gagal: tidak ada respons atau terlalu pendek")
            
            # Coba metode 3: Cek API key
            deepseek_key = os.getenv("DEEPSEEK_API_KEY")
            if deepseek_key and len(deepseek_key) > 10:
                self._log(f"[TEST] API key Deepseek tersedia: {deepseek_key[:5]}...")
            else:
                self._log("[TEST] ❌ API key Deepseek tidak tersedia")
            
            self._log("[TEST] ❌ Semua metode gagal. Pastikan API key Deepseek sudah diset dengan benar.")
            
        except Exception as e:
            self._log(f"[TEST] ❌ Error saat menguji AI: {e}")

    def save_and_init_api(self):
        try:
            api_key = self.key_input.text().strip()
            if not api_key:
                self._log("[ERROR] API Key tidak boleh kosong.")
                return

            self.cfg.set("tr_api_key", api_key)
            self.api = TrakteerAPI(api_key)
            self._log("[INFO] API Key disimpan. Menginisialisasi...")
            
            # Test API dengan refresh saldo
            self.refresh_balance(is_init=True)
        except Exception as e:
            self._log(f"[ERROR] Gagal menginisialisasi API: {e}")
            QMessageBox.warning(self, "Error", f"Gagal menginisialisasi API: {e}")

    def _toggle_listener(self, enabled):
        try:
            if enabled:
                if not self.api:
                    self._log("[ERROR] API belum diinisialisasi. Simpan API Key terlebih dahulu.")
                    self.listener_checkbox.setChecked(False)
                    return

                self._log("[INFO] Mengaktifkan listener donasi...")
                self.last_order_id = None # Reset last order ID
                self.polling_thread = TrakteerPollingThread(self.api.api_key, self.cfg.get("trakteer_poll_interval", 5))
                self.polling_thread.new_support_signal.connect(self._on_new_support)
                self.polling_thread.error_signal.connect(lambda msg: self._log(f"[POLL_ERROR] {msg}"))
                self.polling_thread.start()
            else:
                if self.polling_thread:
                    self._log("[INFO] Menghentikan listener donasi...")
                    self.polling_thread.stop()
                    self.polling_thread = None
        except Exception as e:
            self._log(f"[ERROR] Error toggle listener: {e}")
            self.listener_checkbox.setChecked(False)

    def _get_supporter_name(self, item):
        """
        Ekstrak nama supporter dengan benar dari respons API.
        Sesuai dokumentasi, nama supporter bisa ada di beberapa field.
        """
        # Coba dapatkan nama dari berbagai field yang mungkin
        supporter_name = item.get("supporter_name")
        if supporter_name:
            return supporter_name
            
        # Dokumentasi API menyebutkan creator_name untuk nama supporter
        creator_name = item.get("creator_name")
        if creator_name:
            return creator_name
            
        # Coba dapatkan dari email jika ada
        supporter_email = item.get("supporter_email")
        if supporter_email:
            # Ambil bagian sebelum @ sebagai nama
            return supporter_email.split('@')[0]
            
        # Fallback ke Anonim jika tidak ada informasi
        return "Anonim"

    def _on_new_support(self, item: dict):
        try:
            order_id = item.get("order_id")
            if order_id == self.last_order_id:
                return  # Abaikan duplikat

            self.last_order_id = order_id
            
            # Debug informasi lengkap item
            print(f"[DEBUG] Donation item received: {item}")
            
            # Gunakan fungsi khusus untuk mendapatkan nama supporter
            name = self._get_supporter_name(item)
            quantity = item.get("quantity", 1)
            amount = item.get("amount", 0)
            unit = item.get("unit_name", "")
            message = item.get("support_message", "")

            self._log(f"🎁 Donasi baru dari {name} ({quantity}x {unit} = Rp{amount:,}): \"{message}\"")
            self.muteRequested.emit()

            # Jalankan AI reply di thread terpisah agar UI tidak freeze
            threading.Thread(target=self._generate_ai_reply_worker, args=(name, amount, message), daemon=True).start()
        except Exception as e:
            self._log(f"[ERROR] Error processing new support: {e}")

    # --- Worker Threads ---
    def _generate_ai_reply_worker(self, name, amount, message):
        """Worker untuk menghasilkan balasan AI dan TTS."""
        try:
            # Ambil konteks custom dari CoHost tab jika ada
            custom_context = ""
            main_window = self.window()
            if hasattr(main_window, 'cohost_tab'):
                cohost_tab = main_window.cohost_tab
                if hasattr(cohost_tab, 'cfg'):
                    custom_context = cohost_tab.cfg.get("custom_context", "")
            
            # Buat prompt yang lebih baik
            prompt = f"""
            Kamu adalah AI co-host livestream yang ramah dan ceria.
            Baru saja ada donasi dari "{name}" sebesar Rp{amount:,} dengan pesan: "{message}".
            
            {custom_context}
            
            Tugas Anda:
            1. Sapa "{name}" dengan hangat.
            2. Tanggapi pesannya: "{message}" secara relevan dan natural.
            3. Ucapkan terima kasih atas donasinya.
            4. Berikan doa atau harapan baik.
            
            Gaya bicara harus santai seperti sedang ngobrol, bukan membaca skrip.
            Fokus pada pesan donatur dan berikan jawaban yang memuaskan.
            Jawab dalam bahasa Indonesia dengan maksimal 2 kalimat pendek.
            """
            
            self._log("[AI] Menghasilkan balasan untuk donasi...")
            
            # PERBAIKAN UTAMA: Gunakan client_generate_reply dari modules_client.api
            # yang menggunakan API bridge yang sama dengan cohost_tab
            try:
                self._log("[AI] Mencoba menggunakan client_generate_reply...")
                reply = client_generate_reply(prompt)
                if reply:
                    self._log(f"[AI] Berhasil mendapatkan balasan dari client_generate_reply: {len(reply)} karakter")
                else:
                    self._log("[AI] client_generate_reply gagal, mencoba generate_reply langsung...")
                    reply = generate_reply(prompt)
            except Exception as e:
                self._log(f"[AI] Error client_generate_reply: {e}, mencoba generate_reply langsung...")
                reply = generate_reply(prompt)
            
            if not reply:
                self._log("[AI_WARN] AI tidak menghasilkan balasan. Menggunakan fallback.")
                reply = f"Wah, terima kasih banyak ya, {name}, atas dukungannya! Sehat dan sukses selalu buat kamu!"
            
            # PERBAIKAN: Bersihkan note/instruksi yang tidak perlu ditampilkan
            for marker in ["*Note:", "Note:", "(Note:", "[Note:", "* Note:", "Catatan:", "*Catatan:", "(Catatan:"]:
                if marker in reply:
                    reply = reply.split(marker)[0].strip()
                    break
            
            self._log(f"🤖 AI: {reply}")

            # Panggil TTS Engine
            try:
                main_window = self.window()
                voice_model = self.cfg.get("cohost_voice_model", "id-ID-Standard-A")
                lang_code = "id-ID"
                if hasattr(main_window, 'cohost_tab'):
                     # Gunakan setting dari cohost tab jika ada
                     cohost_tab = main_window.cohost_tab
                     if hasattr(cohost_tab, 'voice_cb') and hasattr(cohost_tab, 'out_lang'):
                        voice_model = cohost_tab.voice_cb.currentData()
                        lang_text = cohost_tab.out_lang.currentText()
                        lang_code = "id-ID" if lang_text == "Indonesia" else "en-US"
                
                self._log(f"[TTS] Memutar suara ({voice_model})...")
                speak(reply, lang_code, voice_model)
            except Exception as e:
                self._log(f"❌ TTS Error: {e}")

        except Exception as e:
            self._log(f"❌ AI Worker Error: {e}")
        finally:
            # Un-mute setelah beberapa detik
            QTimer.singleShot(3000, self.muteReleased.emit)

    def refresh_balance(self, is_init=False):
        if not self.api:
            self._log("[ERROR] API belum diinisialisasi.")
            return

        self.balance_label.setText("Saldo: Memuat...")
        
        def _worker():
            try:
                response = self.api.get_current_balance()
                if response and response.get("status") == "success":
                    balance = float(response.get("result", 0.0))
                    self.balance_label.setText(f"Saldo: Rp{balance:,.2f}")
                    if is_init:
                        self._log("[SUCCESS] Koneksi API berhasil!")
                        # Aktifkan semua fitur setelah koneksi sukses
                        self.listener_checkbox.setEnabled(True)
                        self.refresh_balance_btn.setEnabled(True)
                        self.refresh_history_btn.setEnabled(True)
                else:
                    message = response.get("message", "Gagal mengambil data")
                    self.balance_label.setText("Saldo: Gagal Memuat")
                    self._log(f"[ERROR] Gagal memuat saldo: {message}")
                    if is_init:
                        # Nonaktifkan fitur jika inisialisasi gagal
                        self.listener_checkbox.setEnabled(False)
                        self.refresh_balance_btn.setEnabled(False)
                        self.refresh_history_btn.setEnabled(False)
            except Exception as e:
                self._log(f"[ERROR] Error refreshing balance: {e}")
                self.balance_label.setText("Saldo: Error")

        threading.Thread(target=_worker, daemon=True).start()

    def refresh_support_history(self):
        if not self.api:
            self._log("[ERROR] API belum diinisialisasi.")
            return
            
        self._log("[INFO] Memuat riwayat dukungan...")
        self.history_table.setRowCount(0) # Kosongkan tabel
        
        def _worker():
            try:
                # Gunakan parameter minimal untuk menghindari error 422
                response = self.api.get_supports(limit=10) 
                if response and response.get("status") == "success":
                    data = response.get("result", {}).get("data", [])
                    self.history_table.setRowCount(len(data))
                    for row, item in enumerate(data):
                        self.history_table.setItem(row, 0, QTableWidgetItem(item.get("updated_at", "")))
                        # Gunakan fungsi khusus untuk mendapatkan nama supporter
                        supporter_name = self._get_supporter_name(item)
                        self.history_table.setItem(row, 1, QTableWidgetItem(supporter_name))
                        self.history_table.setItem(row, 2, QTableWidgetItem(f"Rp{item.get('amount', 0):,}"))
                        self.history_table.setItem(row, 3, QTableWidgetItem(f"{item.get('quantity', 1)}x {item.get('unit_name', '')}"))
                        self.history_table.setItem(row, 4, QTableWidgetItem(item.get("support_message", "")))
                    self._log(f"[INFO] Berhasil memuat {len(data)} riwayat dukungan.")
                else:
                    self._log(f"[ERROR] Gagal memuat riwayat: {response.get('message', 'Unknown error')}")
            except Exception as e:
                self._log(f"[ERROR] Error refreshing history: {e}")

        threading.Thread(target=_worker, daemon=True).start()
    
    def closeEvent(self, event):
        """Memastikan thread dihentikan saat aplikasi ditutup."""
        try:
            if self.polling_thread:
                self.polling_thread.stop()
        except Exception as e:
            print(f"Error stopping polling thread: {e}")
        super().closeEvent(event)
