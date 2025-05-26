# modules_client/viewer_memory.py
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

class ViewerMemory:
    def __init__(self, memory_file="config/viewer_memory.json"):
        self.memory_file = Path(memory_file)
        self.memory_file.parent.mkdir(exist_ok=True)
        self.memory_data = self._load_memory()
        
        # Cleanup otomatis saat load
        self._cleanup_old_data()
    
    def _load_memory(self):
        """Load memory dari file JSON"""
        if self.memory_file.exists():
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[ERROR] Load memory gagal: {e}")
                return {}
        return {}
    
    def _save_memory(self):
        """Simpan memory ke file JSON"""
        try:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(self.memory_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[ERROR] Save memory gagal: {e}")
    
    def _cleanup_old_data(self):
        """Hapus data viewer yang lebih dari 30 hari tidak aktif"""
        cutoff_date = datetime.now() - timedelta(days=30)
        to_delete = []
        
        for viewer, data in self.memory_data.items():
            last_seen = data.get("last_seen", "")
            if last_seen:
                try:
                    last_date = datetime.fromisoformat(last_seen)
                    if last_date < cutoff_date:
                        to_delete.append(viewer)
                except:
                    pass
        
        # Hapus viewer lama
        for viewer in to_delete:
            del self.memory_data[viewer]
            print(f"[INFO] Cleanup: Hapus memory viewer {viewer} (>30 hari)")
        
        if to_delete:
            self._save_memory()
    
    def add_interaction(self, viewer_name, message, reply):
        """Tambah interaksi viewer ke memory"""
        now = datetime.now().isoformat()
        
        # Initialize viewer data jika belum ada
        if viewer_name not in self.memory_data:
            self.memory_data[viewer_name] = {
                "first_seen": now,
                "last_seen": now,
                "comment_count": 0,
                "status": "new",
                "recent_interactions": []
            }
        
        viewer_data = self.memory_data[viewer_name]
        
        # Update data
        viewer_data["last_seen"] = now
        viewer_data["comment_count"] += 1
        
        # Update status berdasarkan comment count
        if viewer_data["comment_count"] >= 20:
            viewer_data["status"] = "vip"
        elif viewer_data["comment_count"] >= 5:
            viewer_data["status"] = "regular"
        
        # Tambah interaksi terbaru (max 10)
        interaction = {
            "time": now,
            "message": message,
            "reply": reply
        }
        
        viewer_data["recent_interactions"].append(interaction)
        
        # Keep hanya 10 interaksi terakhir
        if len(viewer_data["recent_interactions"]) > 10:
            viewer_data["recent_interactions"] = viewer_data["recent_interactions"][-10:]
        
        # Save ke file
        self._save_memory()
    
    def get_viewer_info(self, viewer_name):
        """Ambil info viewer dari memory"""
        if viewer_name in self.memory_data:
            return self.memory_data[viewer_name]
        return None
    
    def get_viewer_status(self, viewer_name):
        """Ambil status viewer (new/regular/vip)"""
        viewer_info = self.get_viewer_info(viewer_name)
        if viewer_info:
            return viewer_info.get("status", "new")
        return "new"
    
    def get_recent_context(self, viewer_name, limit=3):
        """Ambil context dari interaksi terakhir"""
        viewer_info = self.get_viewer_info(viewer_name)
        if not viewer_info:
            return ""
        
        interactions = viewer_info.get("recent_interactions", [])[-limit:]
        if not interactions:
            return ""
        
        context_parts = []
        for interaction in interactions:
            time_obj = datetime.fromisoformat(interaction["time"])
            time_str = time_obj.strftime("%H:%M")
            context_parts.append(f"[{time_str}] {interaction['message']} -> {interaction['reply']}")
        
        return " | ".join(context_parts)