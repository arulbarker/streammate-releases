#!/usr/bin/env python3
"""
CREDIT PROTECTION MODULE
========================
Module untuk proteksi real-time sistem kredit.
Auto-import di main.py untuk proteksi otomatis.
"""

import json
import threading
import time
from pathlib import Path
from datetime import datetime

class CreditProtector:
    """Real-time credit protection system"""
    
    def __init__(self):
        self.monitoring = False
        self.last_known_credit = 0
        self.monitor_thread = None
    
    def start_monitoring(self):
        """Start real-time monitoring"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("[PROTECTION] Credit protection monitoring started")
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1)
        print("[PROTECTION] Credit protection monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.monitoring:
            try:
                self._check_credit_integrity()
                time.sleep(30)  # Check every 30 seconds
            except Exception as e:
                print(f"[PROTECTION] Monitor error: {e}")
                time.sleep(60)  # Wait longer on error
    
    def _check_credit_integrity(self):
        """Check credit integrity"""
        try:
            sub_file = Path("config/subscription_status.json")
            if not sub_file.exists():
                return
            
            with open(sub_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            current_credit = data.get("hours_credit", 0)
            
            # Check for unexpected drops
            if (self.last_known_credit > 1000 and 
                current_credit < (self.last_known_credit * 0.5)):
                
                print(f"[PROTECTION] CREDIT DROP DETECTED! {self.last_known_credit} -> {current_credit}")
                self._emergency_restore()
            
            self.last_known_credit = current_credit
            
        except Exception as e:
            print(f"[PROTECTION] Integrity check error: {e}")
    
    def _emergency_restore(self):
        """Emergency credit restore"""
        try:
            from emergency_credit_recovery import main as emergency_main
            print("[PROTECTION] Executing emergency restore...")
            emergency_main()
        except Exception as e:
            print(f"[PROTECTION] Emergency restore failed: {e}")

# Global protector instance
_protector = None

def get_protector():
    """Get global protector instance"""
    global _protector
    if _protector is None:
        _protector = CreditProtector()
    return _protector

def start_protection():
    """Start credit protection"""
    protector = get_protector()
    protector.start_monitoring()

def stop_protection():
    """Stop credit protection"""
    protector = get_protector()
    protector.stop_monitoring()

# Auto-start when imported
if __name__ != "__main__":
    start_protection()
