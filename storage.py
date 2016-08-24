"""
storage.py
Storage abstraction for quizbot.
"""

import sqlite3

import config

DBCON = None

def connect_db():
  global DBCON
  DBCON = sqlite3.connect(config.DATABASE)
