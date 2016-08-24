"""
storage.py
Storage abstraction for quizbot.
"""

import sqlite3
import os

import config

DBCON = None

##########################
# Convenience functions: #
##########################

def mkdir_p(d):
  try:
    os.mkdir(d, 0o750)
  except OSError:
    pass

def opj(*args):
  os.path.join(*args)

####################
# Setup functions: #
####################

def connect_db():
  global DBCON
  if DBCON == None:
    DBCON = sqlite3.connect(config.DATABASE)

def close_db():
  # Note: non-committed changes will be lost!
  if DBCON != None:
    DBCON.rollback()
    DBCON.close()

def init_db():
  cur = DBCON.cursor()
  cur.execute(
    """
    CREATE TABLE IF NOT EXISTS users(
      addr TEXT PRIMARY KEY NOT NULL,
      role TEXT,
      status TEXT
    );
    """
  )
  cur.execute(
    """
    CREATE TABLE IF NOT EXISTS courses(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      school TEXT NOT NULL,
      name TEXT NOT NULL,
      term TEXT NOT NULL,
      year INTEGER NOT NULL
    );
    """
  )
  cur.execute(
    """
    CREATE TABLE IF NOT EXISTS enrollment(
      user TEXT NOT NULL,
      course_id INTEGER NOT NULL,
      status TEXT NOT NULL
    );
    """
  )
  cur.execute(
    """
    CREATE TABLE IF NOT EXISTS assignments(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      course_id INTEGER NOT NULL,
      type TEXT NOT NULL,
      questions TEXT NOT NULL,
      answers TEXT NOT NULL,
      points TEXT NOT NULL,
      value REAL NOT NULL,
      due DATETIME NOT NULL,
      really_due DATETIME,
      reject_after DATETIME
    );
    """
  )
  cur.execute(
    """
    CREATE TABLE IF NOT EXISTS submissions(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user TEXT NOT NULL,
      assignment_id INTEGER NOT NULL,
      timestamp DATETIME NOT NULL,
      content TEXT NOT NULL,
      feedback TEXT NOT NULL,
      grade REAL
    );
    """
  )
  DBCON.commit()

def init_submisisons():
  mkdir_p(config.SUBMISSIONS_DIR)

def setup():
  connect_db()
  init_db()
  init_submisisons()

######################
# Storage functions: #
######################

def add_user(addr, role="default", status="active"):
  cur = DBCON.cursor()
  cur.execute("SELECT addr FROM users WHERE addr = ?;", (addr,))
  results = cur.fetchall()
  if len(results) == 0:
    cur.execute(
      "INSERT INTO users(addr, role, status) values(?, ?, ?);",
      (addr, role, status)
    )
  else:
    if len(results) > 1:
      print("Warning: non-unique user '{}'".format(addr), file=sys.stderr)
    print(
      "Warning: attempt to add existing user '{}'".format(addr),
      file=sys.stderr
    )
  DBCON.commit()

def status(user):
  cur = DBCON.cursor()
  cur.execute("SELECT status FROM users WHERE addr = ?;", (user,))
  results = cur.fetchall()
  if len(results) > 1:
    print("Warning: non-unique user '{}'".format(user), file=sys.stderr)
  elif len(results) == 0:
    return "not-registered"
  return results[0][0] # first result -> only field

def set_status(user, status):
  cur = DBCON.cursor()
  cur.execute("SELECT addr FROM users WHERE addr = ?", (user,))
  results = cur.fetchall()
  if len(results) == 0:
    cur.execute(
      "INSERT INTO users(addr, role, status) values(?, ?, ?);",
      user, "default", status
    )
  else:
    if len(results) > 1:
      print("Warning: non-unique user '{}'".format(user), file=sys.stderr)
    cur.execute(
      "UPDATE users SET status = ? WHERE addr = ?;",
      status, user
    )
  DBCON.commit()

def role(user):
  cur = DBCON.cursor()
  cur.execute("SELECT role FROM users WHERE addr = ?;", (user,))
  results = cur.fetchall()
  if len(results) > 1:
    print("Warning: non-unique user '{}'".format(user), file=sys.stderr)
  elif len(results) == 0:
    return "non-user"
  else:
    return results[0][0] # first result -> only field

def set_role(user, role):
  cur = DBCON.cursor()
  cur.execute("SELECT addr FROM users WHERE addr = ?", (user,))
  results = cur.fetchall()
  if len(results) == 0:
    cur.execute(
      "INSERT INTO users(addr, role, status) values(?, ?, ?);",
      (user, role, "active")
    )
    DBCON.commit()
  else:
    if len(results) > 1:
      print("Warning: non-unique user '{}'".format(user), file=sys.stderr)
    cur.execute(
      "UPDATE users SET role = ? WHERE addr = ?;",
      (role, user)
    )
  DBCON.commit()
