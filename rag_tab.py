# ui/rag_tab.py
import os
import threading
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QTextEdit, QListWidget, QFileDialog, QMessageBox, QTabWidget,
    QLineEdit, QComboBox, QRadioButton, QButtonGroup, QSplitter,
    QCheckBox  # Tambahkan import QCheckBox di sini
)
from PyQt6.QtCore import Qt, pyqtSignal

from modules_client.rag_system import RAGSystem

# Definisikan fungsi update_knowledge_base di sini jika tidak ada di rag_system.py
def update_knowledge_base(kb_name, urls):
    """
    Update knowledge base dari URL.
    
    Args:
        kb_name: Nama knowledge base
        urls: List URL untuk diproses
        
    Returns:
        bool: True jika berhasil
    """
    try:
        # Pastikan direktori ada
        kb_dir = Path("knowledge_bases") / f"{kb_name}_db"
        kb_dir.mkdir(exist_ok=True, parents=True)
        
        # Simpan URL ke file
        with open(kb_dir / "urls.txt", "w", encoding="utf-8") as f:
            for url in urls:
                f.write(f"{url}\n")
        
        # Proses setiap URL
        import requests
        from bs4 import BeautifulSoup
        
        all_content = []
        
        for url in urls:
            try:
                response = requests.get(url, timeout=10)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Hapus script dan style tags
                for script in soup(["script", "style"]):
                    script.decompose()
                
                # Ambil teks
                text = soup.get_text()
                
                # Proses teks (hapus multiple whitespace, dll)
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = '\n'.join(chunk for chunk in chunks if chunk)
                
                all_content.append(f"Source: {url}\n\n{text}")
            except Exception as e:
                print(f"Error processing {url}: {e}")
        
        combined_text = "\n\n---\n\n".join(all_content)
        
        # Simpan konten yang diambil
        with open(kb_dir / "content.txt", "w", encoding="utf-8") as f:
            f.write(combined_text)
        
        # Gunakan RAG system untuk menciptakan embeddingnya
        rag = RAGSystem()
        success = rag.create_kb_from_text(kb_name, combined_text)
        
        return success
        
    except Exception as e:
        print(f"Error in update_knowledge_base: {e}")
        return False

class RAGTab(QWidget):
    """Tab untuk Knowledge Base (RAG) dengan dual mode."""
    
    def __init__(self):
        super().__init__()
        self.rag_system = RAGSystem()
        self.retrieved_docs = []
        self.init_ui()
        self.load_knowledge_bases()
    
    def init_ui(self):
        """Initialize UI elements."""
        layout = QVBoxLayout(self)
        
        # Tab widget untuk mode input
        self.tab_widget = QTabWidget(self)
        
        # Tab 1: Mode Manual (File Upload)
        self.manual_tab = QWidget()
        self.setup_manual_tab()
        self.tab_widget.addTab(self.manual_tab, "📁 Mode Manual")
        
        # Tab 2: Mode Website
        self.website_tab = QWidget()
        self.setup_website_tab()
        self.tab_widget.addTab(self.website_tab, "🌐 Mode Website")
        
        layout.addWidget(self.tab_widget)
        
        # Common section for both modes
        self.setup_common_section(layout)
        
        # Status Label
        self.status_label = QLabel("Status: Ready")
        layout.addWidget(self.status_label)
    
    def setup_manual_tab(self):
        """Setup UI for manual file upload mode."""
        layout = QVBoxLayout(self.manual_tab)
        
        # Document Title
        title = QLabel("Input Knowledge Base Manual")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)
        
        # Document management controls
        doc_controls = QHBoxLayout()
        
        self.btn_add_file = QPushButton("📄 Add Document")
        self.btn_add_file.clicked.connect(self.add_document)
        doc_controls.addWidget(self.btn_add_file)
        
        self.btn_create_index = QPushButton("🔄 Rebuild Index")
        self.btn_create_index.clicked.connect(self.rebuild_index)
        doc_controls.addWidget(self.btn_create_index)
        
        layout.addLayout(doc_controls)
        
        # Document list
        layout.addWidget(QLabel("Available Documents:"))
        self.doc_list = QListWidget()
        layout.addWidget(self.doc_list)
        
        # KB Name for Manual Mode
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Knowledge Base Name:"))
        self.manual_kb_name = QLineEdit()
        self.manual_kb_name.setPlaceholderText("e.g., Coral_Island")
        name_layout.addWidget(self.manual_kb_name)
        
        # Save Button for Manual Mode
        self.save_manual_btn = QPushButton("💾 Save Knowledge Base")
        self.save_manual_btn.clicked.connect(self.save_manual_kb)
        name_layout.addWidget(self.save_manual_btn)
        
        layout.addLayout(name_layout)
    
    def setup_website_tab(self):
        """Setup UI for website scraping mode."""
        layout = QVBoxLayout(self.website_tab)
        
        # Document Title
        title = QLabel("Input Knowledge Base dari Website")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)
        
        # Game Input Section
        game_layout = QHBoxLayout()
        game_layout.addWidget(QLabel("Nama Knowledge Base:"))
        self.game_input = QLineEdit()
        self.game_input.setPlaceholderText("e.g., Stardew_Valley")
        game_layout.addWidget(self.game_input)
        layout.addLayout(game_layout)
        
        # URL Input Section
        layout.addWidget(QLabel("URL Website (satu per baris):"))
        self.url_input = QTextEdit()
        self.url_input.setPlaceholderText("https://example.com/game-guide\nhttps://example.com/game-guide/farming")
        layout.addWidget(self.url_input)
        
        # Process Button
        self.process_btn = QPushButton("🔄 Proses Website")
        self.process_btn.clicked.connect(self.process_website_kb)
        layout.addWidget(self.process_btn)
    
    def setup_common_section(self, layout):
        """Setup common UI elements for both modes."""
        # Divider
        layout.addWidget(QLabel("───────────── Knowledge Base Management ─────────────"))
        
        # KB Management
        kb_select_layout = QHBoxLayout()
        kb_select_layout.addWidget(QLabel("Active Knowledge Base:"))
        self.kb_selector = QComboBox()
        kb_select_layout.addWidget(self.kb_selector)
        
        self.activate_btn = QPushButton("✓ Aktifkan")
        self.activate_btn.clicked.connect(self.activate_kb)
        kb_select_layout.addWidget(self.activate_btn)
        
        self.delete_btn = QPushButton("🗑️ Hapus")
        self.delete_btn.clicked.connect(self.delete_kb)
        kb_select_layout.addWidget(self.delete_btn)
        
        layout.addLayout(kb_select_layout)
        
        # Testing section
        layout.addWidget(QLabel("Test Knowledge Base:"))
        
        # Query input
        query_layout = QHBoxLayout()
        query_layout.addWidget(QLabel("Query:"))
        self.query_input = QLineEdit()
        self.query_input.returnPressed.connect(self.submit_query)
        query_layout.addWidget(self.query_input)
        
        self.btn_submit = QPushButton("🔍 Search")
        self.btn_submit.clicked.connect(self.submit_query)
        query_layout.addWidget(self.btn_submit)
        
        layout.addLayout(query_layout)
        
        # Use RAG checkbox
        self.use_rag_checkbox = QCheckBox("Use Knowledge Base for Co-host responses")
        self.use_rag_checkbox.setChecked(True)
        layout.addWidget(self.use_rag_checkbox)
        
        # Results splitter
        results_layout = QHBoxLayout()
        
        # Retrieved documents
        docs_layout = QVBoxLayout()
        docs_layout.addWidget(QLabel("Retrieved Chunks:"))
        self.retrieved_docs_text = QTextEdit()
        self.retrieved_docs_text.setReadOnly(True)
        docs_layout.addWidget(self.retrieved_docs_text)
        
        # Generated response
        response_layout = QVBoxLayout()
        response_layout.addWidget(QLabel("Generated Response:"))
        self.response_text = QTextEdit()
        self.response_text.setReadOnly(True)
        response_layout.addWidget(self.response_text)
        
        # Add both to results layout
        results_layout.addLayout(docs_layout)
        results_layout.addLayout(response_layout)
        
        layout.addLayout(results_layout)
    
    # Sisanya dari kode sama seperti sebelumnya...
    
    def load_document_list(self):
        """Load list of available documents (untuk mode manual)."""
        try:
            self.doc_list.clear()
            
            # Get documents directory
            docs_dir = Path("knowledge/documents")
            if not docs_dir.exists():
                docs_dir.mkdir(parents=True, exist_ok=True)
                return
            
            # List all text files
            for doc_path in docs_dir.glob("**/*.txt"):
                self.doc_list.addItem(doc_path.name)
            
            self.status_label.setText(f"Loaded {self.doc_list.count()} documents")
        
        except Exception as e:
            self.status_label.setText(f"Error loading documents: {str(e)}")
    
    def load_knowledge_bases(self):
        """Load existing knowledge bases for selector."""
        try:
            kb_dir = Path("knowledge_bases")
            kb_dir.mkdir(exist_ok=True, parents=True)
            
            # Clear and reload
            self.kb_selector.clear()
            
            # List directories ending with _db
            kb_list = [d.name.replace("_db", "") for d in kb_dir.glob("*_db") if d.is_dir()]
            for kb in sorted(kb_list):
                self.kb_selector.addItem(kb)
            
            # Try to select active KB if available
            from modules_client.config_manager import ConfigManager
            cfg = ConfigManager("config/settings.json")
            active_kb = cfg.get("active_knowledge_base", "")
            
            if active_kb:
                index = self.kb_selector.findText(active_kb)
                if index >= 0:
                    self.kb_selector.setCurrentIndex(index)
            
            self.status_label.setText(f"Status: {len(kb_list)} knowledge base ditemukan")
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")
    
    def add_document(self):
        """Add a new document to the knowledge base (manual mode)."""
        try:
            file_dialog = QFileDialog()
            file_path, _ = file_dialog.getOpenFileName(
                self, "Open Text Document", "", "Text Files (*.txt)"
            )
            
            if file_path:
                # Copy file to knowledge directory
                source_path = Path(file_path)
                target_dir = Path("knowledge/documents")
                target_dir.mkdir(parents=True, exist_ok=True)
                
                target_path = target_dir / source_path.name
                
                # Check if file already exists
                if target_path.exists():
                    result = QMessageBox.question(
                        self, 
                        "File Exists", 
                        f"File {source_path.name} already exists. Overwrite?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    
                    if result != QMessageBox.StandardButton.Yes:
                        return
                
                # Copy file
                with open(source_path, 'r', encoding='utf-8') as src_file:
                    text = src_file.read()
                
                with open(target_path, 'w', encoding='utf-8') as tgt_file:
                    tgt_file.write(text)
                
                self.status_label.setText(f"Added document: {source_path.name}")
                
                # Refresh document list
                self.load_document_list()
        
        except Exception as e:
            self.status_label.setText(f"Error adding document: {str(e)}")
    
    def rebuild_index(self):
        """Rebuild the index."""
        try:
            self.status_label.setText("Rebuilding index...")
            
            # Run in a separate thread to not block UI
            def rebuild_thread():
                success = self.rag_system.create_index(rebuild=True)
                
                # Update UI from main thread
                from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
                if success:
                    QMetaObject.invokeMethod(
                        self.status_label, 
                        "setText",
                        Qt.ConnectionType.QueuedConnection,
                        Q_ARG(str, "Index rebuilt successfully")
                    )
                else:
                    QMetaObject.invokeMethod(
                        self.status_label,
                        "setText",
                        Qt.ConnectionType.QueuedConnection,
                        Q_ARG(str, "Failed to rebuild index")
                    )
            
            thread = threading.Thread(target=rebuild_thread)
            thread.daemon = True
            thread.start()
        
        except Exception as e:
            self.status_label.setText(f"Error rebuilding index: {str(e)}")
    
    def save_manual_kb(self):
        """Save knowledge base from manual documents."""
        kb_name = self.manual_kb_name.text().strip()
        
        if not kb_name:
            QMessageBox.warning(self, "Error", "Knowledge base name tidak boleh kosong")
            return
        
        # Check if any documents are available
        doc_count = self.doc_list.count()
        if doc_count == 0:
            QMessageBox.warning(self, "Error", "Tidak ada dokumen untuk disimpan")
            return
        
        self.status_label.setText(f"Status: Menyimpan knowledge base {kb_name}...")
        
        # Process in thread
        thread = threading.Thread(
            target=self._save_manual_kb_thread,
            args=(kb_name,),
            daemon=True
        )
        thread.start()
    
    def _save_manual_kb_thread(self, kb_name):
        """Worker thread for saving manual KB."""
        try:
            # Get document paths
            docs_dir = Path("knowledge/documents")
            doc_paths = list(docs_dir.glob("**/*.txt"))
            
            # Read all documents
            all_texts = []
            for path in doc_paths:
                with open(path, 'r', encoding='utf-8') as f:
                    all_texts.append(f"Source: {path.name}\n\n{f.read()}")
            
            combined_text = "\n\n".join(all_texts)
            
            # Create KB directory
            kb_dir = Path("knowledge_bases") / f"{kb_name}_db"
            kb_dir.mkdir(exist_ok=True, parents=True)
            
            # Save raw content
            with open(kb_dir / "content.txt", "w", encoding="utf-8") as f:
                f.write(combined_text)
            
            # Process and save embeddings
            success = self.rag_system.create_kb_from_text(kb_name, combined_text)
            
            # Update UI
            from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
            if success:
                QMetaObject.invokeMethod(
                    self.status_label,
                    "setText",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, f"Knowledge base {kb_name} berhasil dibuat!")
                )
                
                # Reload knowledge bases
                QMetaObject.invokeMethod(
                    self,
                    "load_knowledge_bases",
                    Qt.ConnectionType.QueuedConnection
                )
            else:
                QMetaObject.invokeMethod(
                    self.status_label,
                    "setText",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, f"Gagal membuat knowledge base {kb_name}")
                )
                
        except Exception as e:
            from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
            QMetaObject.invokeMethod(
                self.status_label,
                "setText",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, f"Error: {str(e)}")
            )
    
    def process_website_kb(self):
        """Process URLs into knowledge base."""
        kb_name = self.game_input.text().strip()
        urls = self.url_input.toPlainText().strip().split("\n")
        urls = [url.strip() for url in urls if url.strip()]
        
        if not kb_name:
            QMessageBox.warning(self, "Error", "Nama knowledge base tidak boleh kosong")
            return
        
        if not urls:
            QMessageBox.warning(self, "Error", "URL tidak boleh kosong")
            return
        
        self.status_label.setText(f"Status: Memproses {len(urls)} URL untuk {kb_name}...")
        
        # Use a separate thread to avoid UI freezing
        thread = threading.Thread(
            target=self._process_website_thread,
            args=(kb_name, urls),
            daemon=True
        )
        thread.start()
    
    def _process_website_thread(self, kb_name, urls):
        """Worker thread for website processing."""
        try:
            # Call the update_knowledge_base function
            success = update_knowledge_base(kb_name, urls)
            
            # Update UI from main thread
            from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
            if success:
                QMetaObject.invokeMethod(
                    self.status_label,
                    "setText",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, f"Status: Knowledge base {kb_name} berhasil dibuat!")
                )
                
                # Reload knowledge bases
                QMetaObject.invokeMethod(
                    self,
                    "load_knowledge_bases",
                    Qt.ConnectionType.QueuedConnection
                )
            else:
                QMetaObject.invokeMethod(
                    self.status_label,
                    "setText",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, f"Gagal membuat knowledge base {kb_name}")
                )
            
        except Exception as e:
            # Show error message
            from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
            QMetaObject.invokeMethod(
                self.status_label,
                "setText",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, f"Error: {str(e)}")
            )
    
    def activate_kb(self):
        """Activate selected knowledge base."""
        selected = self.kb_selector.currentText()
        if not selected:
            QMessageBox.warning(self, "Error", "Pilih knowledge base terlebih dahulu")
            return
        
        # Set as active in configuration
        try:
            from modules_client.config_manager import ConfigManager
            cfg = ConfigManager("config/settings.json")
            cfg.set("active_knowledge_base", selected)
            
            # Load the knowledge base
            success = self.rag_system.set_active_kb(selected)
            
            if success:
                self.status_label.setText(f"Status: Knowledge base {selected} diaktifkan")
            else:
                self.status_label.setText(f"Error: Gagal mengaktifkan knowledge base {selected}")
            
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")
    
    def delete_kb(self):
        """Delete selected knowledge base."""
        selected = self.kb_selector.currentText()
        if not selected:
            QMessageBox.warning(self, "Error", "Pilih knowledge base terlebih dahulu")
            return
        
        # Confirm deletion
        result = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Hapus knowledge base {selected}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if result != QMessageBox.StandardButton.Yes:
            return
        
        try:
            # Delete directory
            kb_dir = Path("knowledge_bases") / f"{selected}_db"
            import shutil
            shutil.rmtree(kb_dir)
            
            # Reload knowledge bases
            self.load_knowledge_bases()
            
            # Reset active KB if it was deleted
            from modules_client.config_manager import ConfigManager
            cfg = ConfigManager("config/settings.json")
            active_kb = cfg.get("active_knowledge_base", "")
            
            if active_kb == selected:
                cfg.set("active_knowledge_base", "")
                self.rag_system.active_kb = None
            
            self.status_label.setText(f"Status: Knowledge base {selected} dihapus")
            
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")
    
    def submit_query(self):
        """Submit a query to the knowledge base."""
        query = self.query_input.text().strip()
        
        if not query:
            return
        
        if not self.rag_system.active_kb:
            QMessageBox.warning(self, "Error", "Aktifkan knowledge base terlebih dahulu")
            return
        
        try:
            self.status_label.setText("Processing query...")
            self.retrieved_docs_text.clear()
            self.response_text.clear()
            
            # Run in a separate thread to not block UI
            def query_thread():
                # Query knowledge base
                response, documents = self.rag_system.generate_with_rag(query)
                
                # Store retrieved documents
                self.retrieved_docs = documents
                
                # Create documents text
                docs_text = ""
                for i, doc in enumerate(documents):
                    docs_text += f"Chunk {i+1}:\n"
                    docs_text += f"Score: {doc['score']:.2f}\n"
                    docs_text += f"{doc['text']}\n\n"
                
                # Update UI from main thread
                from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
                QMetaObject.invokeMethod(
                    self.retrieved_docs_text,
                    "setText",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, docs_text)
                )
                
                QMetaObject.invokeMethod(
                    self.response_text,
                    "setText",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, response)
                )
                
                QMetaObject.invokeMethod(
                    self.status_label,
                    "setText",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, "Query processed")
                )
            
            thread = threading.Thread(target=query_thread)
            thread.daemon = True
            thread.start()
        
        except Exception as e:
            self.status_label.setText(f"Error processing query: {str(e)}")
    
    def is_rag_enabled(self):
        """Check if RAG is enabled."""
        return self.use_rag_checkbox.isChecked()