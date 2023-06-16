import os

from _secrets import *


# Set environment variables
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
os.environ["BOT_TOKEN"] = TELEGRAM_BOT_TOKEN


# Define directories
CHAIN_DIR = "chains"