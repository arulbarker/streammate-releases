"""
StreamMate AI - PyTchat EXE Fix
Solusi definitif untuk masalah pytchat di mode EXE
"""

import sys
import os
import threading
import time
import logging
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass
from queue import Queue, Empty

logger = logging.getLogger(__name__)

class PyTchatEXEFix:
    """Fix untuk pytchat di mode EXE"""
    
    _pytchat = None
    _initialized = False
    
    @classmethod
    def initialize(cls):
        """Initialize pytchat untuk EXE mode"""
        if cls._initialized:
            logger.info(f"PyTchat already initialized: {cls._pytchat is not None}")
            return cls._pytchat is not None
        
        cls._initialized = True
        
        try:
            # Setup environment
            os.environ['PYTCHAT_NO_BROWSER'] = '1'
            os.environ['PYTCHAT_BROWSER'] = 'no_browser'
            
            logger.info("🔄 Attempting to import pytchat...")
            
            # Try import
            import pytchat
            cls._pytchat = pytchat
            logger.info("✅ PyTchat initialized successfully")
            logger.info(f"PyTchat version: {getattr(pytchat, '__version__', 'unknown')}")
            return True
            
        except ImportError as e:
            logger.error(f"❌ Failed to import pytchat: {e}")
            logger.error(f"Python path: {sys.path[:3]}...")  # Show first 3 paths
            cls._pytchat = None
            return False
    
    @classmethod
    def is_available(cls):
        """Check if pytchat is available"""
        if not cls._initialized:
            cls.initialize()
        return cls._pytchat is not None
    
    @classmethod
    def create_chat(cls, video_id=None, channel_id=None):
        """Create chat object"""
        if not cls.is_available():
            raise ImportError("PyTchat not available")
        
        if video_id:
            return cls._pytchat.create(video_id=video_id)
        elif channel_id:
            return cls._pytchat.create(channel_id=channel_id)
        else:
            raise ValueError("Either video_id or channel_id required")

@dataclass
class ChatMessage:
    """Chat message"""
    author: str
    message: str
    timestamp: float
    message_id: str
    is_moderator: bool = False
    is_owner: bool = False

class PyTchatListenerEXE:
    """PyTchat listener untuk EXE mode"""
    
    def __init__(self, video_id: str = None, channel_id: str = None):
        self.video_id = video_id
        self.channel_id = channel_id
        self.chat = None
        self._running = False
        self._thread = None
        self._message_queue = Queue()
        
        # Callbacks
        self.on_message: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        self.on_connect: Optional[Callable] = None
        
    def start(self):
        """Start listening"""
        logger.info(f"🚀 Starting PyTchat listener for: {self.video_id or self.channel_id}")
        
        if not PyTchatEXEFix.is_available():
            error_msg = "PyTchat not available"
            logger.error(error_msg)
            if self.on_error:
                self.on_error(Exception(error_msg))
            return False
        
        if self._running:
            logger.warning("Listener already running")
            return False
        
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        
        logger.info("✅ PyTchat listener thread started successfully")
        return True
    
    def stop(self):
        """Stop listening"""
        self._running = False
        
        if self.chat:
            try:
                self.chat.terminate()
            except:
                pass
            self.chat = None
        
        if self._thread:
            self._thread.join(timeout=5)
        
        logger.info("PyTchat listener stopped")
    
    def _listen_loop(self):
        """Main listening loop"""
        try:
            # CRITICAL FIX: Bypass signal issue by monkey-patching
            import signal
            original_signal = signal.signal
            
            def safe_signal(sig, handler):
                """Safe signal handler that doesn't fail in threads"""
                try:
                    return original_signal(sig, handler)
                except ValueError as e:
                    # "signal only works in main thread" - ignore this error
                    if "main thread" in str(e):
                        logger.warning(f"Signal registration ignored in thread: {e}")
                        return None
                    raise
            
            # Temporarily replace signal.signal
            signal.signal = safe_signal
            
            try:
                # Create chat
                self.chat = PyTchatEXEFix.create_chat(
                    video_id=self.video_id,
                    channel_id=self.channel_id
                )
            finally:
                # Restore original signal function
                signal.signal = original_signal
            
            logger.info(f"Connected to chat: {self.video_id or self.channel_id}")
            
            if self.on_connect:
                self.on_connect()
            
            # Listen for messages
            while self._running and self.chat.is_alive():
                try:
                    for c in self.chat.get().sync_items():
                        if not self._running:
                            break
                        
                        msg = ChatMessage(
                            author=c.author.name,
                            message=c.message,
                            timestamp=time.time(),
                            message_id=getattr(c, 'id', str(time.time())),
                            is_moderator=getattr(c.author, 'isChatModerator', False),
                            is_owner=getattr(c.author, 'isChatOwner', False)
                        )
                        
                        self._message_queue.put(msg)
                        
                        if self.on_message:
                            self.on_message(msg)
                    
                    time.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Error reading messages: {e}")
                    time.sleep(1)
        
        except Exception as e:
            logger.error(f"Chat connection error: {e}")
            if self.on_error:
                self.on_error(e)
    
    def get_messages(self, max_count: int = 100):
        """Get queued messages"""
        messages = []
        while len(messages) < max_count:
            try:
                msg = self._message_queue.get_nowait()
                messages.append(msg)
            except Empty:
                break
        return messages
    
    def is_running(self):
        """Check if running"""
        return self._running and (self._thread and self._thread.is_alive())

# Test function
def test_pytchat():
    """Test pytchat functionality"""
    logger.info("Testing PyTchat...")
    
    if PyTchatEXEFix.initialize():
        logger.info("✅ PyTchat test passed")
        return True
    else:
        logger.error("❌ PyTchat test failed")
        return False

if __name__ == "__main__":
    test_pytchat() 