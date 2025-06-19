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
    
    def _analyze_sentiment(self, text):
        """🔥 NEW: Basic sentiment analysis untuk emotional intelligence"""
        text_lower = text.lower()
        
        # Positive indicators
        positive_words = [
            "bagus", "keren", "mantap", "seru", "asik", "wow", "amazing", 
            "love", "suka", "senang", "happy", "good", "great", "awesome",
            "hebat", "gokil", "perfect", "nice", "cool", "thanks", "terima kasih"
        ]
        
        # Negative indicators  
        negative_words = [
            "boring", "bosan", "jelek", "bad", "buruk", "sedih", "marah",
            "angry", "hate", "benci", "susah", "sulit", "difficult", "problem",
            "masalah", "error", "gagal", "fail", "tidak", "nggak", "ga"
        ]
        
        # Excited indicators
        excited_words = [
            "hype", "excited", "semangat", "mantap", "gokil", "luar biasa",
            "incredible", "unbelievable", "epic", "legendary", "insane"
        ]
        
        # Question/curiosity indicators
        question_words = ["?", "apa", "what", "gimana", "how", "kenapa", "why"]
        
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        excited_count = sum(1 for word in excited_words if word in text_lower)
        question_count = sum(1 for word in question_words if word in text_lower)
        
        # Determine dominant sentiment
        if excited_count >= 1:
            return "excited"
        elif positive_count > negative_count and positive_count >= 1:
            return "positive"
        elif negative_count > positive_count and negative_count >= 1:
            return "negative"
        elif question_count >= 1:
            return "curious"
        else:
            return "neutral"
    
    def _detect_mood_pattern(self, viewer_name, sentiment):
        """🔥 NEW: Detect viewer mood patterns over time"""
        viewer_info = self.get_viewer_info(viewer_name)
        if not viewer_info:
            return "new_viewer"
        
        # Get recent sentiments
        recent_interactions = viewer_info.get("recent_interactions", [])
        if len(recent_interactions) < 3:
            return "getting_to_know"
        
        recent_sentiments = []
        for interaction in recent_interactions[-5:]:  # Last 5 interactions
            msg_sentiment = interaction.get("sentiment", "neutral")
            recent_sentiments.append(msg_sentiment)
        
        # Add current sentiment
        recent_sentiments.append(sentiment)
        
        # Analyze pattern
        positive_ratio = recent_sentiments.count("positive") / len(recent_sentiments)
        excited_ratio = recent_sentiments.count("excited") / len(recent_sentiments)
        negative_ratio = recent_sentiments.count("negative") / len(recent_sentiments)
        
        if excited_ratio >= 0.6:
            return "highly_engaged"
        elif positive_ratio >= 0.7:
            return "consistently_positive"  
        elif negative_ratio >= 0.5:
            return "potentially_disengaged"
        elif recent_sentiments[-2:] == ["negative", "negative"]:
            return "declining_interest"
        elif recent_sentiments[-3:].count("curious") >= 2:
            return "information_seeking"
        else:
            return "stable_engagement"
    
    def _learn_from_interaction(self, viewer_name, message, reply, engagement_score=None):
        """🔥 NEW: Learn from interaction effectiveness"""
        viewer_info = self.get_viewer_info(viewer_name)
        if not viewer_info:
            return
        
        # Initialize learning data if not exists
        if "learning_data" not in viewer_info:
            viewer_info["learning_data"] = {
                "successful_response_patterns": [],
                "preferred_topics": {},
                "response_style_preferences": {
                    "length": "medium",  # short/medium/long
                    "formality": "casual",  # formal/casual/friendly
                    "detail_level": "balanced"  # brief/balanced/detailed
                },
                "engagement_history": []
            }
        
        learning_data = viewer_info["learning_data"]
        
        # Analyze current interaction
        message_type = self._categorize_message(message)
        response_length = len(reply.split())
        
        # Store engagement pattern
        engagement_record = {
            "timestamp": datetime.now().isoformat(),
            "message_type": message_type,
            "response_length": response_length,
            "engagement_score": engagement_score or 0.5,  # Default neutral
            "topic": self._extract_topic(message)
        }
        
        learning_data["engagement_history"].append(engagement_record)
        
        # Keep only last 20 interactions for learning
        if len(learning_data["engagement_history"]) > 20:
            learning_data["engagement_history"] = learning_data["engagement_history"][-20:]
        
        # Update preferred topics
        topic = engagement_record["topic"]
        if topic and engagement_score and engagement_score > 0.6:
            if topic not in learning_data["preferred_topics"]:
                learning_data["preferred_topics"][topic] = 0
            learning_data["preferred_topics"][topic] += 1
        
        # Learn response style preferences
        if engagement_score and engagement_score > 0.7:
            if response_length <= 5:
                learning_data["response_style_preferences"]["length"] = "short"
            elif response_length <= 15:
                learning_data["response_style_preferences"]["length"] = "medium"  
            else:
                learning_data["response_style_preferences"]["length"] = "long"
        
        self._save_memory()
    
    def _categorize_message(self, message):
        """Categorize message type for learning"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["game", "main", "gaming"]):
            return "gaming"
        elif any(word in message_lower for word in ["halo", "hai", "hello"]):
            return "greeting"
        elif "?" in message:
            return "question"
        elif any(word in message_lower for word in ["thanks", "terima kasih", "makasih"]):
            return "appreciation"
        else:
            return "general"
    
    def _extract_topic(self, message):
        """Extract main topic from message"""
        message_lower = message.lower()
        
        topics = {
            "gaming": ["game", "main", "gaming", "play", "rank", "hero"],
            "streaming": ["stream", "streaming", "live", "broadcast"],
            "music": ["musik", "lagu", "song", "music"],
            "technical": ["audio", "video", "lag", "connection"],
            "personal": ["makan", "capek", "tired", "istirahat"]
        }
        
        for topic, keywords in topics.items():
            if any(keyword in message_lower for keyword in keywords):
                return topic
        
        return "general"
    
    def get_optimal_response_style(self, viewer_name):
        """🔥 NEW: Get optimal response style based on learning"""
        viewer_info = self.get_viewer_info(viewer_name)
        if not viewer_info or "learning_data" not in viewer_info:
            return {
                "length": "medium",
                "formality": "casual", 
                "detail_level": "balanced",
                "preferred_topics": []
            }
        
        learning_data = viewer_info["learning_data"]
        style_prefs = learning_data.get("response_style_preferences", {})
        
        # Get top 3 preferred topics
        topic_prefs = learning_data.get("preferred_topics", {})
        sorted_topics = sorted(topic_prefs.items(), key=lambda x: x[1], reverse=True)
        preferred_topics = [topic for topic, count in sorted_topics[:3]]
        
        return {
            "length": style_prefs.get("length", "medium"),
            "formality": style_prefs.get("formality", "casual"),
            "detail_level": style_prefs.get("detail_level", "balanced"), 
            "preferred_topics": preferred_topics
        }

    def add_interaction(self, viewer_name, message, reply, engagement_score=None):
        """Enhanced interaction tracking with sentiment and learning"""
        now = datetime.now().isoformat()
        
        # Analyze sentiment
        sentiment = self._analyze_sentiment(message)
        mood_pattern = self._detect_mood_pattern(viewer_name, sentiment)
        
        # Initialize viewer data jika belum ada
        if viewer_name not in self.memory_data:
            self.memory_data[viewer_name] = {
                "first_seen": now,
                "last_seen": now,
                "comment_count": 0,
                "status": "new",
                "recent_interactions": [],
                "sentiment_history": [],
                "current_mood": mood_pattern
            }
        
        viewer_data = self.memory_data[viewer_name]
        
        # Update data
        viewer_data["last_seen"] = now
        viewer_data["comment_count"] += 1
        viewer_data["current_mood"] = mood_pattern
        
        # Update status berdasarkan comment count
        if viewer_data["comment_count"] >= 20:
            viewer_data["status"] = "vip"
        elif viewer_data["comment_count"] >= 5:
            viewer_data["status"] = "regular"
        
        # Tambah interaksi terbaru dengan sentiment
        interaction = {
            "time": now,
            "message": message,
            "reply": reply,
            "sentiment": sentiment,
            "mood_pattern": mood_pattern
        }
        
        viewer_data["recent_interactions"].append(interaction)
        
        # Keep hanya 10 interaksi terakhir
        if len(viewer_data["recent_interactions"]) > 10:
            viewer_data["recent_interactions"] = viewer_data["recent_interactions"][-10:]
        
        # Update sentiment history
        if "sentiment_history" not in viewer_data:
            viewer_data["sentiment_history"] = []
        viewer_data["sentiment_history"].append({
            "time": now,
            "sentiment": sentiment
        })
        
        # Keep last 20 sentiment records
        if len(viewer_data["sentiment_history"]) > 20:
            viewer_data["sentiment_history"] = viewer_data["sentiment_history"][-20:]
        
        # Learn from this interaction
        self._learn_from_interaction(viewer_name, message, reply, engagement_score)
        
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
        """Ambil context dari interaksi terakhir dengan sentiment awareness"""
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
            sentiment = interaction.get("sentiment", "neutral")
            context_parts.append(f"[{time_str}|{sentiment}] {interaction['message']} -> {interaction['reply']}")
        
        return " | ".join(context_parts)
    
    def get_viewer_preferences(self, viewer_name):
        """Enhanced viewer preferences with learning data"""
        viewer_info = self.get_viewer_info(viewer_name)
        if not viewer_info:
            return {}
        
        interactions = viewer_info.get("recent_interactions", [])
        current_mood = viewer_info.get("current_mood", "stable_engagement")
        
        # Get optimal response style from learning
        optimal_style = self.get_optimal_response_style(viewer_name)
        
        preferences = {
            "common_topics": [],
            "greeting_style": "casual",
            "response_length": optimal_style["length"],
            "last_topics": [],
            "current_mood": current_mood,
            "sentiment_trend": self._get_sentiment_trend(viewer_name),
            "preferred_topics": optimal_style["preferred_topics"],
            "response_style": optimal_style
        }
        
        # Analisis topic yang sering dibahas
        topics = []
        for interaction in interactions:
            message = interaction["message"].lower()
            # Deteksi topic sederhana
            if any(word in message for word in ["game", "gaming", "main"]):
                topics.append("gaming")
            elif any(word in message for word in ["musik", "lagu", "song"]):
                topics.append("music")
            elif any(word in message for word in ["hello", "hi", "halo", "hai"]):
                topics.append("greeting")
        
        # Hitung topic yang paling sering
        from collections import Counter
        topic_counts = Counter(topics)
        preferences["common_topics"] = [topic for topic, count in topic_counts.most_common(3)]
        preferences["last_topics"] = topics[-3:] if topics else []
        
        return preferences
    
    def _get_sentiment_trend(self, viewer_name):
        """Get sentiment trend over recent interactions"""
        viewer_info = self.get_viewer_info(viewer_name)
        if not viewer_info:
            return "neutral"
        
        sentiment_history = viewer_info.get("sentiment_history", [])
        if len(sentiment_history) < 3:
            return "insufficient_data"
        
        recent_sentiments = [s["sentiment"] for s in sentiment_history[-5:]]
        
        positive_count = recent_sentiments.count("positive") + recent_sentiments.count("excited")
        negative_count = recent_sentiments.count("negative")
        
        if positive_count >= 3:
            return "trending_positive"
        elif negative_count >= 2:
            return "trending_negative"
        else:
            return "stable"
    
    def get_personalized_greeting(self, viewer_name):
        """Enhanced personalized greeting with mood awareness"""
        viewer_info = self.get_viewer_info(viewer_name)
        status = self.get_viewer_status(viewer_name)
        mood = viewer_info.get("current_mood", "stable_engagement") if viewer_info else "new_viewer"
        
        # Mood-aware greetings
        if mood == "highly_engaged":
            return f"Wah {viewer_name} semangat banget nih! Gimana kabarnya hari ini?"
        elif mood == "consistently_positive":
            return f"Halo {viewer_name}! Selalu positif ya, keep it up!"
        elif mood == "potentially_disengaged":
            return f"Hey {viewer_name}, apa kabar? Ada yang bisa dibantu?"
        elif mood == "information_seeking":
            return f"Halo {viewer_name}! Ada pertanyaan lagi nih?"
        
        # Status-based fallback
        if status == "new":
            return f"Halo {viewer_name}! Selamat datang di stream!"
        elif status == "regular":
            return f"Hai lagi {viewer_name}! Senang kamu kembali!"
        elif status == "vip":
            return f"Wah {viewer_name} udah datang! Viewer setia nih!"
        
        return f"Halo {viewer_name}!"
    
    def get_viewer_statistics(self):
        """Enhanced statistics with sentiment and mood data"""
        total_viewers = len(self.memory_data)
        
        stats = {
            "total_viewers": total_viewers,
            "new_viewers": 0,
            "regular_viewers": 0,
            "vip_viewers": 0,
            "active_today": 0,
            "active_this_week": 0,
            "top_chatters": [],
            "mood_distribution": {
                "highly_engaged": 0,
                "consistently_positive": 0,
                "stable_engagement": 0,
                "potentially_disengaged": 0,
                "declining_interest": 0,
                "information_seeking": 0
            },
            "sentiment_overview": {
                "positive": 0,
                "negative": 0,
                "neutral": 0,
                "excited": 0,
                "curious": 0
            }
        }
        
        today = datetime.now().date()
        week_ago = datetime.now() - timedelta(days=7)
        
        viewer_activity = []
        
        for viewer, data in self.memory_data.items():
            status = data.get("status", "new")
            stats[f"{status}_viewers"] += 1
            
            # Mood distribution
            mood = data.get("current_mood", "stable_engagement")
            if mood in stats["mood_distribution"]:
                stats["mood_distribution"][mood] += 1
            
            # Recent sentiment analysis
            recent_interactions = data.get("recent_interactions", [])
            if recent_interactions:
                last_sentiment = recent_interactions[-1].get("sentiment", "neutral")
                if last_sentiment in stats["sentiment_overview"]:
                    stats["sentiment_overview"][last_sentiment] += 1
            
            # Check activity
            last_seen = data.get("last_seen", "")
            if last_seen:
                try:
                    last_date = datetime.fromisoformat(last_seen)
                    if last_date.date() == today:
                        stats["active_today"] += 1
                    if last_date >= week_ago:
                        stats["active_this_week"] += 1
                except:
                    pass
            
            # Untuk top chatters
            comment_count = data.get("comment_count", 0)
            viewer_activity.append((viewer, comment_count))
        
        # Sort top chatters
        viewer_activity.sort(key=lambda x: x[1], reverse=True)
        stats["top_chatters"] = viewer_activity[:10]
        
        return stats
