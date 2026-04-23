#!/usr/bin/env python3
"""Initialize database with new status columns"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.database import init_db

init_db()
print("Database initialized successfully!")
