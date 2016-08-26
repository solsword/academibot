"""
storage.py
Storage abstraction for academibot. Backs out to an sqlite3 database and 
"""

# TODO: Real security for auth tokens.

import sqlite3
import os
import datetime

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
    DBCON.row_factory = sqlite3.Row

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
      role TEXT NOT NULL,
      status TEXT NOT NULL,
      auth TEXT NOT NULL
    );
    """
  )
  cur.execute(
    """
    CREATE TABLE IF NOT EXISTS blocking(
      addr TEXT PRIMARY KEY NOT NULL
    );
    """
  )
  cur.execute(
    """
    CREATE TABLE IF NOT EXISTS tokens(
      user TEXT NOT NULL,
      token TEXT NOT NULL,
      purpose TEXT NOT NULL,
      start REAL NOT NULL,
      end REAL NOT NULL
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
      year INTEGER NOT NULL,
      auth TEXT NOT NULL
    );
    """
  )
  cur.execute(
    """
    CREATE TABLE IF NOT EXISTS aliases(
      user TEXT NOT NULL,
      course_id INTEGER NOT NULL,
      alias TEXT NOT NULL
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
      due REAL NOT NULL,
      really_due REAL,
      reject_after REAL
    );
    """
  )
  cur.execute(
    """
    CREATE TABLE IF NOT EXISTS submissions(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user TEXT NOT NULL,
      assignment_id INTEGER NOT NULL,
      timestamp REAL NOT NULL,
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

#####################
# Helper functions: #
#####################

def unique_result(results, errmsg="<unknown>"):
  """
  Takes a set of results returned by fetchall and asserts that there's only
  one, returning None if there are zero results, and the first result
  otherwise. Prints an error message to stderr which includes the optional
  errmsg argument if there is more than one result, and returns False instead
  of None in that case.
  """
  if len(results) == 0:
    return None
  elif len(results) > 1:
    print("Warning: non-unique result {}".format(errmsg), file=sys.stderr)
    return False
  return results[0]

def unique_result_single(results, errmsg="<unknown>"):
  """
  Takes a set of results returned by fetchall and returns the first field of
  the first row, using unique_result to assert that there is only one row. The
  optional errmsg argument gets printed when the result is not unique, and
  False is returned. If there are no results, it returns None.
  """
  row = unique_result(results, errmsg)
  if row:
    return row[0]
  else:
    return row

#############################
# Authentication functions: #
#############################

def now():
  return datetime.datetime.now().timestamp()

def new_auth():
  return ''.join("%02x" % b for b in os.urandom(16))

def check_auth(submitted, against):
  # TODO: hashing, salting, etc. (don't forget 'from' validation)
  return submitted == against

def auth_user(user, auth):
  cur = DBCON.cursor()
  cur.execute("SELECT auth FROM users WHERE addr = ?;", (user,))
  against = unique_result_single(cur.fetchall(), "user '{}'".format(addr))
  if against:
    return check_auth(auth, against)
  else:
    return against

def auth_course(course_id, auth):
  cur = DBCON.cursor()
  cur.execute("SELECT auth FROM courses WHERE id = ?;", (course_id,))
  against = unique_result_single(cur.fetchall(), "course #{}".format(course_id))
  if against:
    return check_auth(auth, against)
  else:
    return against

def auth_token(user, purpose, auth):
  cur = DBCON.cursor()
  cur.execute(
    "SELECT token, start, end FROM tokens WHERE user = ? AND purpose = ?;",
    (user, purpose,)
  )
  rows = cur.fetchall()
  if len(rows) == 0:
    return False
  ts = now()
  for r in rows:
    if r["start"] > ts:
      return False
    if r["end"] < ts:
      return False
    return check_auth(auth, r["token"])

def create_token(
  user,
  purpose,
  start="now",
  duration=config.TEMP_AUTH_INTERVAL
):
  cur = DBCON.cursor()
  if start == "now":
    start = now()
  end = start + duration
  token = new_auth()
  cur.execute(
   "INSERT INTO tokens(user, token, purpose, start, end) values(?, ?, ?, ?, ?)",
    (user, token, purpose, start, end)
  )
  return token

def clean_tokens():
  """
  Removes expired temporary authentication tokens from the database.
  """
  cur = DBCON.cursor()
  ts = now()
  cur.execute("DELETE FROM tokens WHERE end < ?;", (ts,))
  DBCON.commit()

def scramble_user(user):
  cur = DBCON.cursor()
  cur.execute("SELECT addr FROM users WHERE addr = ?;", (user,))
  if len(cur.fetchall()) > 0:
    token = new_auth()
    cur.execute("UPDATE users SET auth = ? WHERE addr = ?;", (token, user))
    DBCON.commit()
    return token
  else:
    return None

def scramble_course(course_id):
  cur = DBCON.cursor()
  cur.execute("SELECT id FROM courses WHERE id = ?;", (course_id,))
  if len(cur.fetchall()) > 0:
    token = new_auth()
    cur.execute("UPDATE courses SET auth = ? WHERE id = ?;", (token, course_id))
    DBCON.commit()
    return token
  else:
    return None

##########################
# More helper functions: #
##########################

def get_course_id(user, id_or_tag_or_alias, id_cache = {}):
  try:
    return int(id_or_tag_or_alias)
  except ValueError:
    spl = id_or_tag_or_alias.split("/")
    cur = DBCON.cursor()
    if len(spl) == 4:
      cur.execute(
        "SELECT id FROM courses WHERE school = ? AND name = ? AND term = ? AND year = ?;",
        spl
      )
      return unique_result_single(cur.fetchall())
    else:
      cur.execute(
        "SELECT id FROM aliases WHERE user = ? AND alias = ?;",
        (user, id_or_tag_or_alias)
      )
      return unique_result_single(cur.fetchall())

def course_tag(course_id, tag_cache = {}):
  if course_id in tag_cache:
    return tag_cache[course_id]
  cur = DBCON.cursor()
  cur.execute(
    "SELECT school, name, term, year FROM courses WHERE id = ?;",
    (course_id,)
  )
  result = "/".join(unique_result(cur.fetchall()))
  tag_cache[course_id] = result
  return result

def aliases_for(user, course_id):
  cur = DBCON.cursor()
  cur.execute(
    "SELECT alias FROM aliases WHERE user = ? AND course_id = ?;",
    (user, course_id)
  )
  return [row[0] for row in cur.fetchall()]

def courses_enrolled(user):
  cur = DBCON.cursor()
  cur.execute(
    "SELECT course_id, status FROM enrollment WHERE user = ?;",
    (user,)
  )
  return cur.fetchall()

def add_user(addr, role="default", status="active"):
  cur = DBCON.cursor()
  cur.execute("SELECT addr FROM users WHERE addr = ?;", (addr,))
  existing = unique_result_single(cur.fetchall())
  if existing or existing == False:
    print(
      "Warning: attempt to add existing user '{}'".format(addr),
      file=sys.stderr
    )
  else:
    auth = new_auth()
    cur.execute(
      "INSERT INTO users(addr, role, status, auth) values(?, ?, ?, ?);",
      (addr, role, status, auth)
    )
  DBCON.commit()
  return auth

#####################
# Status functions: #
#####################

def is_registered(user):
  cur = DBCON.cursor()
  cur.execute("SELECT addr FROM users WHERE addr = ?", (user,))
  result = unique_result_single(cur.fetchall(), "user '{}'".format(user))
  if result == None:
    return False
  else:
    return True

def set_block(user):
  cur = DBCON.cursor()
  cur.execute("SELECT addr FROM blocking WHERE addr = ?;", (user,))
  if len(cur.fetchall()) == 0:
    cur.execute("INSERT INTO blocking(addr) values(?);", (user,))
    DBCON.commit()

def remove_block(user):
  cur = DBCON.cursor()
  cur.execute("DELETE FROM blocking WHERE addr = ?;", (user,))
  DBCON.commit()

def status(user):
  cur = DBCON.cursor()
  cur.execute("SELECT status FROM users WHERE addr = ?;", (user,))
  result = unique_result_single(cur.fetchall(), "user '{}'".format(user))
  if result == None:
    return "not-registered"
  elif result == False:
    return "multiple-identity"
  else:
    return result

def set_status(user, status):
  if not is_registered(user):
    add_user(user)
  cur = DBCON.cursor()
  cur.execute(
    "UPDATE users SET status = ? WHERE addr = ?;",
    status, user
  )
  DBCON.commit()

def role(user):
  cur = DBCON.cursor()
  cur.execute("SELECT role FROM users WHERE addr = ?;", (user,))
  result = unique_result_single(cur.fetchall(), "user '{}'".format(user))
  if not result:
    return "non-user"
  else:
    return result

def set_role(user, role):
  if not is_registered(user):
    add_user(user)
  cur = DBCON.cursor()
  cur.execute(
    "UPDATE users SET role = ? WHERE addr = ?;",
    (role, user)
  )
  DBCON.commit()

def enrollment_status(user, course_id):
  cur = DBCON.cursor()
  cur.execute(
    "SELECT status FROM enrollment WHERE user = ? AND course_id = ?;",
    (user, course_id)
  )
  result = unique_result_single(
    cur.fetchall(),
    "user '{}'/course_id #{}".format(
      user,
      course_id
    )
  )
  return result or "none"

def add_instructor(course_id, user):
  enr = enrollment_status(user, course_id)
  if enr == "none":
    cur = DBCON.cursor()
    cur.execute(
      "INSERT INTO enrollment(user, course_id, status) values(?, ?, ?);",
      (user, course_id, "instructor")
    )
    DBCON.commit()
    return (
      True,
      "Set user '{}' to be an instructor for course {}".format(
        user,
        course_tag(course_id)
      )
    )
  else:
    cur = DBCON.cursor()
    cur.execute(
      "UPDATE enrollment set status = ? WHERE user = ? AND course_id = ?;",
      ("instructor", user, course_id)
    )
    DBCON.commit()
    return (
      True,
      "Added user '{}' as an instructor for course {}".format(
        user,
        course_tag(course_id)
      )
    )

def expect_student(course_id, user):
  enr = enrollment_status(user, course_id)
  if enr == "expected":
    return (
      False,
      "User '{}' is already expected for course {}.".format(
        user,
        course_tag(course_id)
      )
    )
  elif enr == "enrolled":
    return (
      False,
      "User '{}' is already enrolled in course {}.".format(
        user,
        course_tag(course_id)
      )
    )
  elif enr != "none":
    cur = DBCON.cursor()
    cur.execute(
      "UPDATE enrollment set status = ? WHERE user = ? AND course_id = ?;",
      ("expected", user, course_id)
    )
    DBCON.commit()
    return (
      True,
      "Set enrollment status to 'expected' for user '{}' in course {}".format(
        user,
        course_tag(course_id)
      )
    )
  else:
    cur = DBCON.cursor()
    cur.execute(
      "INSERT INTO enrollment(user, course_id, status) values(?, ?, ?);",
      (user, course_id, "expected")
    )
    DBCON.commit()
    return (
      True,
      "Added user '{}' as an 'expected' student for course {}".format(
        user,
        course_tag(course_id)
      )
    )

def enroll_student(course_id, user):
  enr = enrollment_status(user, course_id)
  if enr == "expected":
    cur = DBCON.cursor()
    cur.execute(
      "UPDATE enrollment set status = ? WHERE user = ? AND course_id = ?;",
      ("enrolled", user, course_id)
    )
    DBCON.commit()
    return (
      True,
      "Enrolled expected user '{}' in course {}.".format(
        user,
        course_tag(course_id)
      )
    )
  elif enr == "enrolled":
    return (
      False,
      "User '{}' is already enrolled in course {}.".format(
        user,
        course_tag(course_id)
      )
    )
  else:
    return (
      False,
      "User '{}' is not expected to enroll in course {}. Contact your instructor and make sure that you're on the course roster.".format(
        user,
        course_tag(course_id)
      )
    )
