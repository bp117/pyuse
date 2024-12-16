"""
magentic_flow_worker.py
Stand-alone module that manages userQueue -> multi-step flow -> botQueue
"""

import time
import random
import queue
import threading

# Global queues (or you could pass them in):
userQueue = queue.Queue()
botQueue = queue.Queue()

def magentic_flow_worker():
    """
    Continuously processes userQueue.
    For each (username, message), simulates multi-step replies,
    enqueues each step to botQueue.
    """
    while True:
        username, message = userQueue.get()  # block until a user msg is available
        if message is None:
            break  # sentinel to stop

        steps = [
            f"Parsing your request: '{message}'",
            "Validating payment details...",
            "Repairing transaction records...",
            "Verifying final statuses...",
            "Payment repair completed successfully!"
        ]
        emoji_list = ["🤖", "💡", "🔧", "✅", "✨", "📁", "🕑"]

        for step in steps:
            time.sleep(1)  # 1s delay per step
            reply = f"{random.choice(emoji_list)} {step}"
            botQueue.put(reply)

# If you want to run this standalone for debugging:
if __name__ == "__main__":
    worker_thread = threading.Thread(target=magentic_flow_worker, daemon=True)
    worker_thread.start()

    # Example usage: push a message
    userQueue.put(("You", "Hello from external worker"))
    
    # Print out bot replies
    while True:
        if not botQueue.empty():
            msg = botQueue.get()
            print("Bot:", msg)
        time.sleep(0.2)
