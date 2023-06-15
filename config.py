import os

from _secrets import *


# Set environment variables
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY



# Define directories
CHAIN_DIR = "chains"