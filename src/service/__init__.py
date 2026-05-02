import os
import sys

# Dynamically add the 'src' directory to sys.path so absolute imports work when running via uvicorn from root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

from .service import app

__all__ = ["app"]
