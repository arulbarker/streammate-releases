# modules_client/dev_credit_tracker.py
import json
import time
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger('StreamMate')

class DevCreditTracker:
    """Credit tracker khusus untuk developer mode dengan tracking real tapi unlimited."""
    
    def __init__(self):
        self.subscription_file = Path("config/subscription_status.json")
        self.session_start = None
        self.total_usage = 0
        
    def start_tracking(self, feature_name="dev_test"):
        """Mulai tracking untuk developer mode."""
        self.session_start = time.time()
        logger.info(f"Dev tracking started for: {feature_name}")
        
    def stop_tracking(self):
        """Stop tracking dan update file (tapi tidak kurangi kredit)."""
        if not self.session_start:
            return 0
            
        session_duration = time.time() - self.session_start
        minutes_used = session_duration / 60
        
        logger.info(f"Dev tracking stopped - Duration: {minutes_used:.2f} minutes")
        
        # Update file untuk tracking tapi jangan kurangi kredit
        self._update_usage_stats(minutes_used)
        
        self.session_start = None
        return minutes_used
        
    def _update_usage_stats(self, minutes_used):
        """Update statistics tapi jangan kurangi kredit actual."""
        if not self.subscription_file.exists():
            return
            
        try:
            with open(self.subscription_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Update usage stats untuk tracking
            if "dev_usage_stats" not in data:
                data["dev_usage_stats"] = {}
                
            today = datetime.now().strftime('%Y-%m-%d')
            if today not in data["dev_usage_stats"]:
                data["dev_usage_stats"][today] = 0
                
            data["dev_usage_stats"][today] += minutes_used / 60  # Convert to hours
            
            # Update timestamp tapi JANGAN kurangi hours_credit
            data["updated_at"] = datetime.now().isoformat()
            data["dev_last_session"] = {
                "minutes": minutes_used,
                "timestamp": datetime.now().isoformat()
            }
            
            # Save
            with open(self.subscription_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                
            logger.info(f"Dev usage stats updated: +{minutes_used:.2f} minutes")
            
        except Exception as e:
            logger.error(f"Error updating dev usage stats: {e}")