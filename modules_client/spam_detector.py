import time
import hashlib
from typing import Dict, List, Tuple
from collections import defaultdict
from difflib import SequenceMatcher

class SpamDetector:
    """Detect dan filter spam messages dari user."""
    
    def __init__(self):
        # User message history: {username: [(timestamp, message, hash), ...]}
        self.user_history: Dict[str, List[Tuple[float, str, str]]] = defaultdict(list)
        
        # Blocked users: {username: unblock_timestamp}
        self.blocked_users: Dict[str, float] = {}
        
        # Configuration
        self.similarity_threshold = 0.8  # 80% similar = spam
        self.spam_window = 60  # Check spam dalam 60 detik
        self.max_spam_count = 3  # 3x spam = block
        self.block_duration = 300  # Block 5 menit
        self.history_limit = 10  # Keep last 10 messages per user
    
    def _hash_message(self, message: str) -> str:
        """Create hash dari message untuk quick comparison."""
        normalized = message.lower().strip()
        # Remove common variations
        for word in ["bang", "bro", "gan", "min", "kak"]:
            normalized = normalized.replace(word, "")
        normalized = ''.join(c for c in normalized if c.isalnum() or c.isspace())
        return hashlib.md5(normalized.encode()).hexdigest()[:8]
    
    def _calculate_similarity(self, msg1: str, msg2: str) -> float:
        """Calculate similarity antara 2 messages."""
        # Quick check dengan hash
        if self._hash_message(msg1) == self._hash_message(msg2):
            return 1.0
        
        # Detailed similarity check
        return SequenceMatcher(None, msg1.lower(), msg2.lower()).ratio()
    
    def is_spam(self, username: str, message: str) -> Tuple[bool, str]:
        """
        Check apakah message adalah spam.
        Returns: (is_spam, reason)
        """
        current_time = time.time()
        
        # Check if user is blocked
        if username in self.blocked_users:
            if current_time < self.blocked_users[username]:
                remaining = int(self.blocked_users[username] - current_time)
                return True, f"User diblokir ({remaining}s)"
            else:
                # Unblock user
                del self.blocked_users[username]
        
        # Get user history
        user_messages = self.user_history[username]
        
        # Add current message
        msg_hash = self._hash_message(message)
        user_messages.append((current_time, message, msg_hash))
        
        # Keep only recent messages
        user_messages = [
            msg for msg in user_messages 
            if current_time - msg[0] < self.spam_window
        ]
        
        # Limit history size
        if len(user_messages) > self.history_limit:
            user_messages = user_messages[-self.history_limit:]
        
        self.user_history[username] = user_messages
        
        # Check for spam patterns
        spam_count = 0
        similar_messages = []
        
        for i, (ts1, msg1, hash1) in enumerate(user_messages[:-1]):
            similarity = self._calculate_similarity(msg1, message)
            
            if similarity >= self.similarity_threshold:
                spam_count += 1
                similar_messages.append(msg1)
                
                # Quick check: exact same message
                if hash1 == msg_hash:
                    spam_count += 1
        
        # Evaluate spam
        if spam_count >= self.max_spam_count:
            # Block user
            self.blocked_users[username] = current_time + self.block_duration
            return True, f"Spam terdeteksi ({spam_count} pesan serupa)"
        
        elif spam_count > 0:
            # Warning but not block yet
            return True, f"Pesan mirip terdeteksi ({spam_count}x)"
        
        return False, ""
    
    def get_user_stats(self, username: str) -> Dict:
        """Get statistics for specific user."""
        messages = self.user_history.get(username, [])
        
        return {
            "total_messages": len(messages),
            "is_blocked": username in self.blocked_users,
            "block_time_remaining": max(0, self.blocked_users.get(username, 0) - time.time()),
            "recent_messages": [msg[1] for msg in messages[-5:]]
        }
    
    def get_overall_stats(self) -> Dict:
        """Get overall spam detection stats."""
        return {
            "total_users": len(self.user_history),
            "blocked_users": len(self.blocked_users),
            "total_messages": sum(len(msgs) for msgs in self.user_history.values()),
            "active_blocks": list(self.blocked_users.keys())
        }
    
    def clear_old_data(self):
        """Clean old data to save memory."""
        current_time = time.time()
        
        # Clear old messages
        for username in list(self.user_history.keys()):
            messages = self.user_history[username]
            recent_messages = [
                msg for msg in messages 
                if current_time - msg[0] < self.spam_window * 2
            ]
            
            if recent_messages:
                self.user_history[username] = recent_messages
            else:
                del self.user_history[username]
        
        # Clear expired blocks
        expired_blocks = [
            username for username, unblock_time in self.blocked_users.items()
            if current_time >= unblock_time
        ]
        
        for username in expired_blocks:
            del self.blocked_users[username]
