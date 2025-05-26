# modules_client/rag_system.py
import os
import json
import time
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

def split_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """Split text into chunks with overlap."""
    chunks = []
    for i in range(0, len(text), chunk_size - overlap):
        chunk = text[i:i + chunk_size]
        if chunk:  # Skip empty chunks
            chunks.append(chunk)
    return chunks

def update_knowledge_base(kb_name: str, urls: List[str]) -> bool:
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

class SimpleRAG:
    """Implementasi sederhana RAG tanpa ketergantungan eksternal."""
    
    def __init__(self, path):
        self.document_path = path
        self.documents = []
        
    def add_document(self, text, source="user"):
        """Tambahkan dokumen ke basis pengetahuan."""
        self.documents.append({
            "source": source,
            "text": text,
            "id": len(self.documents)
        })
        return True
        
    def search(self, query, k=3):
        """Cari dokumen yang relevan."""
        results = []
        for doc in self.documents:
            # Pencocokan sederhana berdasarkan kata kunci
            score = 0
            for word in query.lower().split():
                if word in doc["text"].lower():
                    score += 1
            
            if score > 0:
                results.append({
                    "text": doc["text"],
                    "source": doc["source"],
                    "score": score
                })
        
        # Urutkan berdasarkan skor
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:k]

class RAGSystem:
    """
    Retrieval Augmented Generation (RAG) system.
    Versi sederhana tanpa ketergantungan eksternal.
    """
    
    def __init__(self, knowledge_dir: str = "knowledge"):
        """
        Initialize RAG system.
        
        Args:
            knowledge_dir: Directory containing knowledge documents
        """
        self.knowledge_dir = Path(knowledge_dir)
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)
        
        # Menggunakan implementasi RAG sederhana
        self.documents = []
        self.index = SimpleRAG(self.knowledge_dir)
        
        # Inisialisasi active KB
        self.active_kb = None
        self.active_kb_metadata = {}
        
        # Load dokumen jika ada
        self._load_documents()
    
    def _load_documents(self):
        """Load documents from knowledge directory."""
        docs_dir = self.knowledge_dir / "documents"
        if not docs_dir.exists():
            docs_dir.mkdir(parents=True)
            return
        
        # Load semua file teks
        for doc_path in docs_dir.glob("**/*.txt"):
            try:
                text = doc_path.read_text(encoding="utf-8")
                self.documents.append({
                    "text": text,
                    "source": str(doc_path),
                    "chunk_id": 0
                })
                
                # Tambahkan ke indeks pencarian
                self.index.add_document(text, str(doc_path))
            except Exception as e:
                print(f"Error loading document {doc_path}: {e}")
    
    def create_index(self, rebuild: bool = False) -> bool:
        """
        Create or rebuild index dari dokumen.
        Versi sederhana - hanya memuat ulang dokumen.
        """
        self.documents = []
        self.index = SimpleRAG(self.knowledge_dir)
        self._load_documents()
        return True
    
    def query(self, query_text: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Query knowledge base for relevant documents.
        """
        # Cek jika ada active KB
        if self.active_kb:
            return self._query_active_kb(query_text, top_k)
            
        # Gunakan pencarian sederhana jika tidak ada active KB
        results = self.index.search(query_text, top_k)
        
        # Format ulang hasil
        formatted_results = []
        for idx, res in enumerate(results):
            formatted_results.append({
                "text": res["text"],
                "source": res["source"],
                "chunk_id": idx,
                "score": res.get("score", 0),
                "distance": 1.0 - (res["score"] / (len(query_text.split()) + 0.1))
            })
            
        return formatted_results
    
    def _query_active_kb(self, query_text: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Query active knowledge base."""
        if not self.active_kb:
            return []
           
        try:
            kb_dir = Path("knowledge_bases") / f"{self.active_kb}_db"
            
            # Cari file chunks
            chunks = list(kb_dir.glob("chunk_*.txt"))
            
            results = []
            for chunk_path in chunks:
                text = chunk_path.read_text(encoding="utf-8")
                
                # Hitung skor sederhana
                score = 0
                for word in query_text.lower().split():
                    if word in text.lower():
                        score += 1
                
                if score > 0:
                    results.append({
                        "text": text,
                        "source": str(chunk_path),
                        "score": score,
                        "chunk_id": int(chunk_path.stem.split("_")[1])
                    })
            
            # Urutkan berdasarkan skor dan ambil top k
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:top_k]
            
        except Exception as e:
            print(f"Error querying active KB: {e}")
            return []
    
    def add_document(self, text: str, source: str = "user_input") -> bool:
        """
        Add new document to knowledge base.
        """
        try:
            # Create directory if not exists
            docs_dir = self.knowledge_dir / "documents"
            docs_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename from source
            filename = f"{source.replace(' ', '_')}_{int(time.time())}.txt"
            file_path = docs_dir / filename
            
            # Write document
            file_path.write_text(text, encoding="utf-8")
            
            # Add to documents list
            self.documents.append({
                "text": text,
                "source": str(file_path),
                "chunk_id": 0
            })
            
            # Add to search index
            self.index.add_document(text, str(file_path))
            
            return True
            
        except Exception as e:
            print(f"Error adding document: {e}")
            return False
    
    def set_active_kb(self, kb_name: str) -> bool:
        """
        Set active knowledge base.
        
        Args:
            kb_name: Nama knowledge base
            
        Returns:
            bool: True jika berhasil
        """
        try:
            # Path ke knowledge base
            kb_dir = Path("knowledge_bases") / f"{kb_name}_db"
            
            if not kb_dir.exists():
                print(f"Knowledge base {kb_name} not found")
                return False
            
            # Simpan referensi
            self.active_kb = kb_name
            
            # Load metadata jika ada
            metadata_path = kb_dir / "metadata.json"
            if metadata_path.exists():
                with open(metadata_path, "r", encoding="utf-8") as f:
                    self.active_kb_metadata = json.load(f)
            
            print(f"Active KB set to: {kb_name}")
            return True
        except Exception as e:
            print(f"Error setting active KB: {e}")
            return False
            
    def create_kb_from_text(self, kb_name: str, text: str) -> bool:
        """Create knowledge base from raw text."""
        try:
            # Clean KB Name
            kb_name = kb_name.replace(" ", "_")
            
            # Create directory structure
            kb_dir = Path("knowledge_bases") / f"{kb_name}_db"
            kb_dir.mkdir(exist_ok=True, parents=True)
            
            # Save raw content
            with open(kb_dir / "content.txt", "w", encoding="utf-8") as f:
                f.write(text)
            
            # Split content into chunks for better retrieval
            chunks = split_text(text)
            
            # Check if SentenceTransformer is available
            try:
                from sentence_transformers import SentenceTransformer
                has_embeddings = True
            except ImportError:
                has_embeddings = False
                print("SentenceTransformer not available. Using keyword-based indexing instead.")
            
            # Process chunks
            for i, chunk in enumerate(chunks):
                # Save chunk for reference
                chunk_file = kb_dir / f"chunk_{i}.txt"
                chunk_file.write_text(chunk, encoding="utf-8")
                
                # Add to standard index
                self.index.add_document(chunk, str(chunk_file))
                
                # Add to documents list
                self.documents.append({
                    "text": chunk,
                    "source": str(chunk_file),
                    "chunk_id": i,
                    "kb_name": kb_name
                })
            
            # Create embeddings if supported
            if has_embeddings:
                # Create embedding model
                model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
                
                # Process chunks and create embeddings
                embeddings = []
                for chunk in chunks:
                    embedding = model.encode(chunk)
                    embeddings.append(embedding)
                
                # Save embeddings as numpy array for fast retrieval
                embeddings_array = np.array(embeddings)
                np.save(kb_dir / "embeddings.npy", embeddings_array)
            
            # Save metadata
            import datetime
            with open(kb_dir / "metadata.json", "w", encoding="utf-8") as f:
                json.dump({
                    "name": kb_name,
                    "type": "manual",
                    "chunks": len(chunks),
                    "has_embeddings": has_embeddings,
                    "created_at": datetime.datetime.now().isoformat()
                }, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"Error creating knowledge base: {e}")
            return False
    
    def generate_with_rag(self, query: str, prompt_template: str = "{context}\n\nQuestion: {query}\n\nAnswer:") -> Tuple[str, List[Dict[str, Any]]]:
        """
        Generate response with RAG.
        """
        # Retrieve relevant documents
        documents = self.query(query)
        
        if not documents:
            # No relevant documents found
            return "No relevant information found.", []
        
        # Create context from documents
        context_parts = []
        for i, doc in enumerate(documents):
            context_parts.append(f"[{i+1}] {doc['text']}")
        
        context = "\n\n".join(context_parts)
        
        # Create prompt
        prompt = prompt_template.format(context=context, query=query)
        
        try:
            # Generate response using available API
            response = None
            
            # Try different APIs
            apis_to_try = [
                # Tuple of (module_path, function_name)
                ("modules_server.deepseek_ai", "generate_reply"),
                ("modules_client.api", "generate_reply")
            ]
            
            for module_path, function_name in apis_to_try:
                try:
                    module = __import__(module_path, fromlist=[function_name])
                    function = getattr(module, function_name)
                    response = function(prompt)
                    if response:
                        break
                except ImportError:
                    continue
                except Exception as e:
                    print(f"Error calling {module_path}.{function_name}: {e}")
            
            if response:
                return response, documents
            else:
                return "Could not generate a response. API unavailable.", documents
            
        except Exception as e:
            print(f"Error generating response: {e}")
            return f"Error generating response: {str(e)}", documents