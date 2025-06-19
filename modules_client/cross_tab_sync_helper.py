# modules_client/cross_tab_sync_helper.py
"""
Cross-Tab Synchronization Helper
Memastikan semua tab (CoHost, Profile, Subscription) menampilkan data kredit yang sinkron
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

class CrossTabSyncHelper:
    """Helper untuk sinkronisasi data kredit antar tab"""
    
    def __init__(self):
        self.subscription_file = Path("config/subscription_status.json")
        self.notification_file = Path("temp/credit_notification.json")
        
    def get_current_credit_data(self) -> Dict[str, Any]:
        """Dapatkan data kredit terkini dari file subscription"""
        try:
            if not self.subscription_file.exists():
                return {
                    "hours_credit": 0.0,
                    "hours_used": 0.0,
                    "status": "inactive",
                    "error": "No subscription file found"
                }
            
            with open(self.subscription_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            hours_credit = float(data.get("credit_balance", data.get("hours_credit", 0)))
            hours_used = float(data.get("credit_used", data.get("hours_used", 0)))
            
            return {
                "hours_credit": hours_credit,
                "hours_used": hours_used,
                "remaining_credits": hours_credit * 60,  # Convert to credits
                "status": data.get("status", "inactive"),
                "package": data.get("package", "none"),
                "last_deduction": data.get("last_deduction", {}),
                "updated_at": data.get("updated_at", ""),
                "error": None
            }
            
        except Exception as e:
            return {
                "hours_credit": 0.0,
                "hours_used": 0.0,
                "status": "error",
                "error": str(e)
            }
    
    def notify_all_tabs_credit_update(self, credits_used: float, description: str = ""):
        """Buat notifikasi untuk semua tab bahwa kredit telah berubah"""
        try:
            current_data = self.get_current_credit_data()
            
            notification = {
                "type": "credit_update",
                "timestamp": datetime.now().isoformat(),
                "credits_used": credits_used,
                "description": description,
                "current_data": current_data,
                "message": f"Kredit berkurang {credits_used:.2f}. Sisa: {current_data['hours_credit']:.2f} jam"
            }
            
            # Create notification file for UI updates
            self.notification_file.parent.mkdir(exist_ok=True, parents=True)
            with open(self.notification_file, 'w', encoding='utf-8') as f:
                json.dump(notification, f, indent=2)
            
            print(f"[SYNC] Credit update notification created for all tabs")
            print(f"[SYNC] {notification['message']}")
            
            return True
            
        except Exception as e:
            print(f"[SYNC] Error creating notification: {e}")
            return False
    
    def force_refresh_all_tabs(self):
        """Trigger refresh untuk semua tab yang support"""
        try:
            # Create refresh signal file
            refresh_signal = Path("temp/force_refresh_signal.json")
            refresh_signal.parent.mkdir(exist_ok=True, parents=True)
            
            signal_data = {
                "timestamp": datetime.now().isoformat(),
                "action": "force_refresh_credits",
                "trigger": "cross_tab_sync"
            }
            
            with open(refresh_signal, 'w', encoding='utf-8') as f:
                json.dump(signal_data, f, indent=2)
            
            print(f"[SYNC] Force refresh signal created for all tabs")
            return True
            
        except Exception as e:
            print(f"[SYNC] Error creating refresh signal: {e}")
            return False
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Dapatkan status sinkronisasi untuk debugging"""
        current_data = self.get_current_credit_data()
        
        return {
            "subscription_file_exists": self.subscription_file.exists(),
            "notification_file_exists": self.notification_file.exists(),
            "current_credits": current_data.get("hours_credit", 0),
            "current_usage": current_data.get("hours_used", 0),
            "last_update": current_data.get("updated_at", ""),
            "status": current_data.get("status", "unknown")
        }

# Global instance untuk akses mudah
cross_tab_sync = CrossTabSyncHelper()

def notify_credit_change(credits_used: float, description: str = ""):
    """Shortcut function untuk notifikasi perubahan kredit"""
    return cross_tab_sync.notify_all_tabs_credit_update(credits_used, description)

def force_all_tabs_refresh():
    """Shortcut function untuk force refresh semua tab"""
    return cross_tab_sync.force_refresh_all_tabs()

def get_unified_credit_data():
    """Shortcut function untuk mendapatkan data kredit terpadu"""
    return cross_tab_sync.get_current_credit_data() 