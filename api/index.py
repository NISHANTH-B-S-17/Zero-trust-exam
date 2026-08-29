import os
import sys

# Add root and backend to sys.path so imports resolve smoothly on Vercel
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from backend.app.main import app
