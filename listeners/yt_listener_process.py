#!/usr/bin/env python3
"""
YouTube Chat Listener - Meant to be run in a separate process.
Connects to Pytchat and puts new messages into a multiprocessing.Queue.
"""

import sys
import time
from pathlib import Path

# Add project root to path to allow imports
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

def youtube_chat_worker(video_id: str, message_queue, log_queue):
    """
    The main worker function for the Pytchat process.

    Args:
        video_id (str): The YouTube video ID to connect to.
        message_queue (multiprocessing.Queue): The queue to put new chat messages into.
        log_queue (multiprocessing.Queue): The queue for sending log messages back to the main app.
    """
    # Fix for Windows console encoding in separate processes
    if sys.platform == "win32":
        import io
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
        except Exception as e:
            log_queue.put(("ERROR", f"Failed to set UTF-8 encoding in process: {e}"))

    log_queue.put(("INFO", f"Pytchat process started for video: {video_id}"))

    # Import pytchat inside the worker function
    try:
        import pytchat
    except ImportError:
        log_queue.put(("ERROR", "Pytchat is not installed or available in the process."))
        return

    chat = None
    retry_delay = 5
    max_retries = 3

    for attempt in range(max_retries):
        try:
            chat = pytchat.create(video_id=video_id)
            log_queue.put(("SUCCESS", f"Successfully connected to YouTube Live: {video_id}"))
            break
        except Exception as e:
            log_queue.put(("ERROR", f"Connection attempt {attempt+1}/{max_retries} failed: {e}"))
            if attempt < max_retries - 1:
                log_queue.put(("INFO", f"Retrying in {retry_delay} seconds..."))
                time.sleep(retry_delay)
                retry_delay *= 2 # Exponential backoff
            else:
                log_queue.put(("ERROR", "All connection attempts failed. Terminating listener process."))
                return

    while chat and chat.is_alive():
        try:
            for c in chat.get().sync_items():
                # Put a tuple of (author, message) into the queue
                message_queue.put((c.author.name, c.message))
        except Exception as e:
            log_queue.put(("WARNING", f"Error fetching chat data: {e}"))
            # If an error occurs, wait a bit before trying again to avoid spamming errors
            time.sleep(5)

    log_queue.put(("INFO", "Listener process is terminating."))

if __name__ == '__main__':
    # This part allows for direct testing of the script, but it won't be used by the main app.
    # The main app will import and run the `youtube_chat_worker` function in a process.
    print("This script is designed to be run as a process from the main application.")
    print("To test, you would need to provide a video_id and a queue.") 