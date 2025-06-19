"""
StreamMate AI - Enhanced PyTchat Listener
Fixed untuk bekerja di development dan production mode
"""

import sys
import os
import threading
import time
import json
import logging
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass
from queue import Queue, Empty

# Setup logging
logger = logging.getLogger(__name__)

# ========== PYTCHAT IMPORT HANDLER ==========
class PyTchatImporter:
    """Handle pytchat import untuk semua environment"""
    
    @staticmethod
    def setup_paths():
        """Setup all possible pytchat paths"""
        if getattr(sys, 'frozen', False):
            app_root = Path(sys.executable).parent
        else:
            app_root = Path(__file__).resolve().parent.parent
        
        # All possible locations
        locations = [
            app_root / "thirdparty" / "pytchat_ng",
            app_root / "thirdparty" / "pytchat",
            app_root / "_internal" / "pytchat",
            app_root / "_internal" / "pytchat_ng",
            Path("thirdparty") / "pytchat_ng",  # Relative
            Path("thirdparty") / "pytchat",     # Relative
        ]
        
        # Add to sys.path
        for loc in locations:
            if loc.exists():
                parent = str(loc.parent) if loc.name.startswith("pytchat") else str(loc)
                if parent not in sys.path:
                    sys.path.insert(0, parent)
                    logger.info(f"Added to sys.path: {parent}")
        
        # Set environment
        os.environ['PYTCHAT_NO_BROWSER'] = '1'
        os.environ['PYTCHAT_BROWSER'] = 'no_browser'
    
    @staticmethod
    def import_pytchat():
        """Import pytchat with fallbacks"""
        PyTchatImporter.setup_paths()
        
        # Try standard import first
        try:
            import pytchat
            logger.info("PyTchat imported successfully (standard)")
            return pytchat
        except ImportError as e:
            logger.warning(f"Standard import failed: {e}")
        
        # Try from specific locations
        if getattr(sys, 'frozen', False):
            app_root = Path(sys.executable).parent
        else:
            app_root = Path(__file__).resolve().parent.parent
        
        # Manual import attempts
        locations = [
            app_root / "thirdparty" / "pytchat_ng",
            app_root / "thirdparty" / "pytchat",
        ]
        
        for loc in locations:
            if not loc.exists():
                continue
                
            try:
                # Add location
                if str(loc.parent) not in sys.path:
                    sys.path.insert(0, str(loc.parent))
                
                # Create __init__.py if missing
                init_file = loc / "__init__.py"
                if not init_file.exists():
                    init_file.touch()
                
                # Try import again
                import pytchat
                logger.info(f"PyTchat imported from {loc}")
                return pytchat
            except ImportError:
                continue
        
        raise ImportError("Failed to import pytchat from all locations")

# Import pytchat
try:
    pytchat = PyTchatImporter.import_pytchat()
except ImportError as e:
    logger.error(f"Failed to import pytchat: {e}")
    pytchat = None

# ========== CHAT MESSAGE CLASS ==========
@dataclass
class ChatMessage:
    """Standardized chat message"""
    author: str
    message: str
    timestamp: float
    message_id: str
    is_moderator: bool = False
    is_owner: bool = False
    is_member: bool = False
    is_verified: bool = False
    currency: str = ""
    amount: float = 0.0
    
    def to_dict(self):
        return {
            "author": self.author,
            "message": self.message,
            "timestamp": self.timestamp,
            "message_id": self.message_id,
            "is_moderator": self.is_moderator,
            "is_owner": self.is_owner,
            "is_member": self.is_member,
            "is_verified": self.is_verified,
            "currency": self.currency,
            "amount": self.amount
        }

# ========== PYTCHAT LISTENER CLASS ==========
class PytchatListener:
    """Enhanced PyTchat listener with error handling"""
    
    def __init__(self, video_id: str = None, channel_id: str = None):
        self.video_id = video_id
        self.channel_id = channel_id
        self.chat = None
        self._running = False
        self._thread = None
        self._message_queue = Queue()
        self._error_count = 0
        self._max_errors = 5
        self._retry_delay = 5
        
        # Callbacks
        self.on_message: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        self.on_connect: Optional[Callable] = None
        self.on_disconnect: Optional[Callable] = None
        
        logger.info(f"PytchatListener initialized - Video: {video_id}, Channel: {channel_id}")
    
    def start(self):
        """Start listening to chat"""
        if not pytchat:
            error_msg = "PyTchat not available - cannot start listener"
            logger.error(error_msg)
            if self.on_error:
                self.on_error(Exception(error_msg))
            return False
        
        if self._running:
            logger.warning("Listener already running")
            return False
        
        self._running = True
        self._error_count = 0
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        
        logger.info("PyTchat listener started")
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
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        
        logger.info("PyTchat listener stopped")
    
    def _listen_loop(self):
        """Main listening loop with reconnection"""
        while self._running:
            try:
                # Create chat object
                if self.video_id:
                    self.chat = pytchat.create(video_id=self.video_id)
                    logger.info(f"Connected to video chat: {self.video_id}")
                elif self.channel_id:
                    self.chat = pytchat.create(channel_id=self.channel_id)
                    logger.info(f"Connected to channel chat: {self.channel_id}")
                else:
                    raise ValueError("No video_id or channel_id provided")
                
                # Reset error count on successful connection
                self._error_count = 0
                
                # Notify connection
                if self.on_connect:
                    self.on_connect()
                
                # Read messages
                while self._running and self.chat.is_alive():
                    try:
                        for c in self.chat.get().sync_items():
                            if not self._running:
                                break
                            
                            # Process message
                            msg = self._process_chat_item(c)
                            if msg:
                                self._message_queue.put(msg)
                                if self.on_message:
                                    self.on_message(msg)
                        
                        # Small delay to prevent CPU overuse
                        time.sleep(0.1)
                        
                    except Exception as e:
                        # Don't log common pytchat internal errors unless debugging
                        if "Operation on a closed object" not in str(e):
                            logger.error(f"Error reading chat items: {e}", exc_info=False)
                        time.sleep(1)
                
            except pytchat.exceptions.NoPageFound as e:
                logger.error(f"Pytchat Error: NoPageFound. The stream may not be live or has ended. {e}")
                self._running = False # Stop the loop
                if self.on_error:
                    self.on_error(e)

            except Exception as e:
                logger.error(f"Chat connection error: {e}", exc_info=True)
                self._error_count += 1
                
                if self.on_error:
                    self.on_error(e)
                
                if self._error_count >= self._max_errors:
                    logger.error("Max errors reached - stopping listener")
                    self._running = False
                    break
                
                logger.info(f"Retrying in {self._retry_delay} seconds... ({self._error_count}/{self._max_errors})")
                time.sleep(self._retry_delay)
            
            finally:
                if self.chat:
                    try:
                        self.chat.terminate()
                    except:
                        pass
                    self.chat = None
                
                if self.on_disconnect:
                    self.on_disconnect()
            
            logger.info("Listener loop has finished.")
    
    def _process_chat_item(self, item) -> Optional[ChatMessage]:
        """
        Safely process a single chat item from pytchat.
        This is the CORE fix to prevent crashes from unexpected data structures.
        """
        try:
            # Check for superchat/fan funding
            if item.type == 'superChat' or item.type == 'fanFundingEvent':
                currency = getattr(item, 'currency', 'N/A')
                amount = getattr(item, 'amountValue', 0.0)
                message_content = f"SUPERCHAT: {item.message}" if item.message else "SUPERCHAT"
            else:
                currency = ""
                amount = 0.0
                message_content = item.message

            if not message_content:
                return None

            return ChatMessage(
                author=item.author.name,
                message=message_content,
                timestamp=item.timestamp / 1000.0,  # Convert ms to seconds
                message_id=item.id,
                is_moderator=item.author.isChatModerator,
                is_owner=item.author.isChatOwner,
                is_member=item.author.isChatSponsor,
                is_verified=item.author.isVerified,
                currency=currency,
                amount=amount
            )
        except (AttributeError, ValueError, TypeError) as e:
            # This block catches errors if the 'item' object from pytchat
            # doesn't have the expected attributes (like author.name, message, etc.)
            # or if there's a value unpacking issue.
            logger.warning(f"Could not process chat item due to malformed data: {e}. Item: {item.json()}", exc_info=False)
            return None
    
    def get_messages(self, max_count: int = 100) -> list[ChatMessage]:
        """Get queued messages"""
        messages = []
        
        while len(messages) < max_count:
            try:
                msg = self._message_queue.get_nowait()
                messages.append(msg)
            except Empty:
                break
        
        return messages
    
    def is_running(self) -> bool:
        """Check if listener is running"""
        return self._running and (self._thread and self._thread.is_alive())

# ========== HELPER FUNCTIONS ==========
def test_pytchat_import():
    """Test if pytchat can be imported"""
    try:
        pytchat_module = PyTchatImporter.import_pytchat()
        print(f"✓ PyTchat imported successfully")
        print(f"  Location: {pytchat_module.__file__ if hasattr(pytchat_module, '__file__') else 'Unknown'}")
        return True
    except Exception as e:
        print(f"✗ PyTchat import failed: {e}")
        return False

def get_youtube_id_from_url(url: str) -> tuple[str, str]:
    """Extract video_id or channel_id from YouTube URL"""
    import re
    
    # Video ID patterns
    video_patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed\/)([0-9A-Za-z_-]{11})',
        r'(?:watch\?v=)([0-9A-Za-z_-]{11})',
    ]
    
    for pattern in video_patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1), 'video'
    
    # Channel patterns
    channel_patterns = [
        r'(?:channel\/)([UC][0-9A-Za-z_-]{21}[AQgw])',
        r'(?:c\/)([0-9A-Za-z_-]+)',
        r'(?:@)([0-9A-Za-z_-]+)',
    ]
    
    for pattern in channel_patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1), 'channel'
    
    return None, None

# ========== MAIN TEST ==========
if __name__ == "__main__":
    print("PyTchat Listener Test")
    print("=" * 50)
    
    # Test import
    if not test_pytchat_import():
        print("Failed to import pytchat!")
        sys.exit(1)
    
    # Test listener
    print("\nTesting listener...")
    
    # Example video ID (ganti dengan live stream ID)
    test_video = "jfKfPfyJRdk"  # Example: lofi hip hop radio
    
    listener = PytchatListener(video_id=test_video)
    
    # Set callbacks
    def on_message(msg: ChatMessage):
        print(f"[CHAT] {msg.author}: {msg.message}")
    
    def on_error(error):
        print(f"[ERROR] {error}")
    
    def on_connect():
        print("[CONNECTED] Successfully connected to chat")
    
    def on_disconnect():
        print("[DISCONNECTED] Disconnected from chat")
    
    listener.on_message = on_message
    listener.on_error = on_error
    listener.on_connect = on_connect
    listener.on_disconnect = on_disconnect
    
    # Start listening
    if listener.start():
        print("Listener started! Press Ctrl+C to stop...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping...")
            listener.stop()
    else:
        print("Failed to start listener!")