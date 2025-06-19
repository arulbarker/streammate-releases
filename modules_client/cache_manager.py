import json
import time
import hashlib
from pathlib import Path
from typing import Dict, Optional, Tuple
import random

class CacheManager:
    """Smart cache untuk response AI dengan variasi natural."""
    
    def __init__(self, cache_dir: str = "temp/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "response_cache.json"
        self.cache = self._load_cache()
        self.cache_ttl = 1800  # 30 menit
        
        # Template variations untuk natural response
        self.greeting_variations = [
            "Halo {name}! Welcome",
            "Hi {name}, senang kamu join",
            "Hello {name}, apa kabar?",
            "Hai {name}, selamat datang!",
            "Wah ada {name}, welcome!"
        ]
        
        self.game_question_variations = [
            "Lagi seru main {game} nih!",
            "Main {game} dulu gan",
            "Sekarang lagi fokus {game}",
            "Lagi asik {game} bro"
        ]
        
        self.thanks_variations = [
            "Thanks banget {name}!",
            "Makasih ya {name}",
            "Wah terima kasih {name}",
            "Thank you {name}!",
            "Makasih banyak {name}"
        ]
    
    def _load_cache(self) -> Dict:
        """Load cache dari file."""
        if self.cache_file.exists():
            try:
                return json.loads(self.cache_file.read_text(encoding="utf-8"))
            except:
                return {}
        return {}
    
    def _save_cache(self):
        """Save cache ke file."""
        self.cache_file.write_text(json.dumps(self.cache, indent=2), encoding="utf-8")
    
    def _generate_key(self, message: str, context: str = "") -> str:
        """Generate cache key dari message."""
        # Normalize message
        normalized = message.lower().strip()
        normalized = ''.join(c for c in normalized if c.isalnum() or c.isspace())
        
        # Create hash
        content = f"{normalized}:{context}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def _is_expired(self, timestamp: float) -> bool:
        """Check apakah cache expired."""
        return time.time() - timestamp > self.cache_ttl
    
    def get_cached_response(self, message: str, context: Dict) -> Optional[str]:
        """Get response dari cache dengan smart matching."""
        # Clean expired entries
        self._clean_expired()
        
        # Try exact match first
        key = self._generate_key(message, context.get("game", ""))
        if key in self.cache:
            entry = self.cache[key]
            if not self._is_expired(entry["timestamp"]):
                return self._personalize_response(
                    entry["response"], 
                    context.get("author", "teman")
                )
        
        # Try pattern matching
        pattern_response = self._match_pattern(message, context)
        if pattern_response:
            return pattern_response
        
        return None
    
    def cache_response(self, message: str, response: str, context: Dict):
        """Cache response dengan metadata."""
        key = self._generate_key(message, context.get("game", ""))
        
        self.cache[key] = {
            "message": message,
            "response": response,
            "context": context,
            "timestamp": time.time(),
            "hits": 0
        }
        
        # Limit cache size (LRU)
        if len(self.cache) > 100:
            self._evict_lru()
        
        self._save_cache()
    
    def _match_pattern(self, message: str, context: Dict) -> Optional[str]:
        """Match message dengan pattern dan return response."""
        msg_lower = message.lower().strip()
        author = context.get("author", "teman")
        
        # Greeting patterns
        greetings = ["halo", "hello", "hi", "hai", "pagi", "siang", "sore", "malam"]
        for greet in greetings:
            if greet in msg_lower:
                return random.choice(self.greeting_variations).format(name=author)
        
        # Game question patterns
        game_questions = ["main apa", "game apa", "lagi main", "apa yang dimain", "maen apa"]
        for question in game_questions:
            if question in msg_lower:
                game = context.get("game", "game")
                response = random.choice(self.game_question_variations).format(game=game)
                return response
        
        # Thanks patterns
        thanks_words = ["makasih", "terima kasih", "thank", "thanks", "tq"]
        for thank in thanks_words:
            if thank in msg_lower:
                return random.choice(self.thanks_variations).format(name=author)
        
        # Rank/tier questions
        rank_questions = ["rank", "tier", "division", "medal"]
        for rank_q in rank_questions:
            if rank_q in msg_lower:
                rank = context.get("rank", "Epic")
                return f"Sekarang di rank {rank} nih {author}"
        
        return None
    
    def _personalize_response(self, response: str, author: str) -> str:
        """Personalize cached response dengan nama user."""
        # Replace placeholder dengan actual name
        placeholders = ["{name}", "[nama]", "{author}", "[user]"]
        for placeholder in placeholders:
            response = response.replace(placeholder, author)
        
        # Add variation suffix sometimes (20% chance)
        if random.random() < 0.2:
            suffixes = [" hehe", " nih", " gan", " bro", " kak"]
            response += random.choice(suffixes)
        
        return response
    
    def _clean_expired(self):
        """Clean expired cache entries."""
        current_time = time.time()
        expired_keys = []
        
        for key, entry in self.cache.items():
            if self._is_expired(entry["timestamp"]):
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            self._save_cache()
    
    def _evict_lru(self):
        """Evict least recently used entries."""
        # Sort by timestamp (oldest first)
        sorted_entries = sorted(
            self.cache.items(), 
            key=lambda x: x[1]["timestamp"]
        )
        
        # Remove oldest 20%
        remove_count = len(self.cache) // 5
        for key, _ in sorted_entries[:remove_count]:
            del self.cache[key]
        
        self._save_cache()
    
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        total_entries = len(self.cache)
        total_hits = sum(entry.get("hits", 0) for entry in self.cache.values())
        
        return {
            "total_entries": total_entries,
            "total_hits": total_hits,
            "cache_size_kb": self.cache_file.stat().st_size / 1024 if self.cache_file.exists() else 0,
            "hit_rate": total_hits / (total_entries + 1) * 100 if total_entries > 0 else 0
        }
