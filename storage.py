"""
storage.py
Storage abstraction for academibot. Backs out to an sqlite3 database and 
"""

# TODO: Real security for auth tokens.

import sqlite3
import os
import stat
import datetime
import collections
import sys

import config

import formats
import grading

REQ_F = collections.namedtuple(
  "request",
  ["type", "value", "status"]
)

ENR_F = collections.namedtuple(
  "enrollment",
  ["course_id", "user", "status"]
)

SUB_F = collections.namedtuple(
  "submission",
  ["id", "assignment_id", "user", "timestamp", "content", "feedback", "grade"]
)

DBCON = None

LINE_LENGTH = 80

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

def connect_db(db_name):
  global DBCON
  if DBCON == None:
    chmod = False
    if not os.path.exists(db_name):
      chmod = True
    DBCON = sqlite3.connect(db_name)
    DBCON.row_factory = sqlite3.Row
    if chmod:
      os.chmod(
        db_name,
        stat.S_IRWXU # 0700
      )

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
      institution TEXT NOT NULL,
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
    CREATE TABLE IF NOT EXISTS requests(
      user TEXT NOT NULL,
      type TEXT NOT NULL,
      value TEXT NOT NULL,
      status TEXT NOT NULL
    );
    """
  )
  cur.execute(
    """
    CREATE TABLE IF NOT EXISTS assignments(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      course_id INTEGER NOT NULL,
      name TEXT NOT NULL,
      flags TEXT NOT NULL,
      publish_at REAL NOT NULL,
      due_at REAL NOT NULL,
      late_after REAL,
      reject_after REAL,
      content TEXT NOT NULL
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

def setup(db_name):
  connect_db(db_name)
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

def now_ts():
  return datetime.datetime.now().timestamp()

def new_auth():
  return ''.join("%02x" % b for b in os.urandom(16))

def check_auth(submitted, against):
  # TODO: hashing, salting, etc. (don't forget 'from' validation)
  return submitted == against

def auth_user(user, auth):
  cur = DBCON.cursor()
  cur.execute("SELECT auth FROM users WHERE addr = ?;", (user,))
  against = unique_result_single(cur.fetchall(), "user '{}'".format(user))
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

def auth_token(now, user, purpose, auth):
  cur = DBCON.cursor()
  cur.execute(
    "SELECT token, start, end FROM tokens WHERE user = ? AND purpose = ?;",
    (user, purpose,)
  )
  rows = cur.fetchall()
  if len(rows) == 0:
    return False
  for r in rows:
    if r["start"] > now:
      return False
    if r["end"] < now:
      return False
    return check_auth(auth, r["token"])

def create_token(
  user,
  purpose,
  now,
  start="now",
  duration=config.TEMP_AUTH_INTERVAL
):
  cur = DBCON.cursor()
  if start == "now":
    start = now
  end = start + duration
  token = new_auth()
  cur.execute(
   "INSERT INTO tokens(user, token, purpose, start, end) values(?, ?, ?, ?, ?);",
    (user, token, purpose, start, end)
  )
  return token

def clean_tokens():
  """
  Removes expired temporary authentication tokens from the database.
  """
  cur = DBCON.cursor()
  ts = now_ts()
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
        "SELECT id FROM courses WHERE institution = ? AND name = ? AND term = ? AND year = ?;",
        spl
      )
      return unique_result_single(
        cur.fetchall(),
        "course {}/{}/{}/{}".format(
          spl[0],
          spl[1],
          spl[2],
          spl[3]
        )
      )
    else:
      cur.execute(
        "SELECT course_id FROM aliases WHERE user = ? AND alias = ?;",
        (user, id_or_tag_or_alias)
      )
      return unique_result_single(
        cur.fetchall(),
        "alias '{}'".format(id_or_tag_or_alias)
      )

def course_tag(course_id, tag_cache = {}):
  # TODO: course renaming...
  if course_id in tag_cache:
    return tag_cache[course_id]
  cur = DBCON.cursor()
  cur.execute(
    "SELECT institution, name, term, year FROM courses WHERE id = ?;",
    (course_id,)
  )
  row = unique_result(cur.fetchall(), "course #{}".format(course_id))
  if row:
    result = "/".join(str(x) for x in row)
    tag_cache[course_id] = result
    return result
  else:
    return "<unknown course #{}>".format(course_id)

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
  existing = unique_result_single(cur.fetchall(), "user '{}'".format(addr))
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
  cur.execute("SELECT addr FROM users WHERE addr = ?;", (user,))
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

def all_enrollments(user):
  cur = DBCON.cursor()
  cur.execute(
    "SELECT course_id, user, status FROM enrollment WHERE user = ?;",
    (user,)
  )
  return [ ENR_F(*r) for r in cur.fetchall() ]

def enrolled_users(course_id):
  cur = DBCON.cursor()
  cur.execute(
    "SELECT course_id, user, status FROM enrollment WHERE course_id = ?;",
    (course_id,)
  )
  return [ ENR_F(*r) for r in cur.fetchall() ]

######################
# Request functions: #
######################

def process_request(user, typ, value):
  cur = DBCON.cursor()
  if typ == "role":
    cur.execute(
      "SELECT addr FROM users WHERE addr = ?;",
      (user,)
    )
    if len(cur.fetchall()) == 0:
      return (False, "User '{}' is not registered.\n".format(user))
    cur.execute(
      "UPDATE users SET role = ? WHERE addr = ?;",
      (value, user)
    )
    DBCON.commit()
    return (True, "Set role to {} for user '{}'.\n".format(value, user))
  else:
    return (False, "Unknown permission type {}.\n".format(typ))


def outstanding_requests(user=None):
  cur = DBCON.cursor()
  if user:
    cur.execute("SELECT typ, value, status FROM requests;")
  else:
    cur.execute(
      "SELECT typ, value, status FROM requests WHERE user = ?;",
      (user,)
    )
  [REQ_F(*row) for row in cur.fetchall()]

def submit_request(user, typ, value):
  cur = DBCON.cursor()
  cur.execute(
    "SELECT status FROM requests WHERE user = ? AND type = ? AND value = ?;",
    (user, typ, value)
  )
  rows = cur.fetchall()
  if any(r[0] == "requested" for r in rows):
    return (
      False,
      "Previous request for {}/{} by user '{}' is still outstanding.\n".format(
        typ, value, user
      )
    )
  if any(r[0] == "granted" for r in rows):
    success, msg = process_request(user, typ, value)
    if not success:
      return (
        False,
        "Error processing request {}/{}: {}".format(typ, value, msg)
      )
    cur.execute(
      "DELETE FROM requests WHERE user = ? AND type = ? AND value = ?;",
      (user, typ, value)
    )
    DBCON.commit()
    return (
      True,
      """
Request {}/{} pre-authorized for user '{}'.

{}
""".format(typ, value, user, msg)
    )

  cur.execute(
    "DELETE FROM requests WHERE user = ? AND type = ? AND value = ?;",
    (user, typ, value)
  )
  cur.execute(
    "INSERT INTO requests(user, type, value, status) values(?, ?, ?, ?);",
    (user, typ, value, "requested")
  )
  DBCON.commit()
  return (
    True,
    """\
Request {typ}/{value} submitted for user '{user}'.

A user with appropriate role/permissions must use:

:grant {user} {typ} {value}

to approve this request.
""".format(typ=typ, value=value, user=user)
  )

def grant_request(user, typ, value):
  cur = DBCON.cursor()
  cur.execute(
    "SELECT status FROM requests WHERE user = ? AND type = ? AND value = ?;"
    (user, typ, value)
  )
  rows = cur.fetchall()

  if any(r[0] == "requested" for r in rows):
    success, msg = process_request(user, typ, value)
    if not success:
      return (
        False,
        "Error processing request {}/{}: {}".format(typ, value, msg)
      )
    cur.execute(
      "DELETE FROM requests WHERE user = ? AND type = ? AND value = ?;",
      (user, typ, value)
    )
    DBCON.commit()
    return (
      True,
      """
Granted requested permission {}/{} for user '{}'.

{}
""".format(typ, value, user, msg)
    )

  if any(r[0] == "granted" for r in rows):
    return (
      False,
      "Previous permission {}/{} for user '{}' has not been used.\n".format(
        typ, value, user
      )
    )

  cur.execute(
    "DELETE FROM requests WHERE user = ? AND type = ? AND value = ?;",
    (user, typ, value)
  )
  cur.execute(
    "INSERT INTO requests(user, type, value, status) values(?, ?, ?, ?);",
    (user, typ, value, "granted")
  )
  DBCON.commit()
  return (
    True,
    """\
Added permission {typ}/{value} for user '{user}'.

User '{user}' has not yet requested this permission. They can use:

:request {typ} {value}

to do so.
""".format(typ=typ, value=value, user=user)
  )

################################
# Course management functions: #
################################

def create_course(user, institution, name, term, year):
  cur = DBCON.cursor()
  cur.execute(
    "SELECT id FROM courses WHERE institution = ? AND name = ? AND term = ? AND year = ?;",
    (institution, name, term, year)
  )
  if len(cur.fetchall()) > 0:
    return (
      False,
      "Error: Course {}/{}/{}/{} already exists.\n".format(
        institution,
        name,
        term,
        year
      )
    )
  token = new_auth()
  cur.execute(
    "INSERT INTO courses(institution, name, term, year, auth) values(?, ?, ?, ?, ?);",
    (institution, name, term, year, token)
  )
  cur.execute(
    "SELECT id FROM courses WHERE institution = ? AND name = ? AND term = ? AND year = ?;",
    (institution, name, term, year)
  )
  course_id = cur.fetchall()[0][0]
  DBCON.commit()
  add_instructor(course_id, user)
  return (
    True,
    """\
Created course {inst}/{name}/{term}/{year} and added user '{user}' as an instructor. The course ID is {id}. For course management, the authentication token is:

{token}

Make sure that you save this token and keep it private; anyone with the token can manage the course. If you need to reset the token, send:

:auth {inst}/{name}/{term}/{year} {token}
:scramble {inst}/{name}/{term}/{year}

To add students to this course send:

:auth {inst}/{name}/{term}/{year} {token}
:expect {inst}/{name}/{term}/{year} <list of student emails>

Students can then enroll in the course by sending:

:enroll {inst}/{name}/{term}/{year}
""".format(
  id = course_id,
  inst = institution,
  name = name,
  term = term,
  year = year,
  token = token,
  user = user
)
  )

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
  elif enr == "instructor":
    return (
      False,
      "User '{}' is an instructor in course {} (!)".format(
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

#########################
# Assignment functions: #
#########################

def create_assignment(course_id, assignment):
  # Check and normalize assignment structure:
  valid, err = formats.process_assignment(assignment)
  if not valid:
    return (False, err)
  raw = formats.unparse(assignment)

  # Check that the course exists:
  cur = DBCON.cursor()
  cur.execute("SELECT id FROM courses WHERE id = ?;",(course_id,))
  valid = unique_result_single(cur.fetchall(), "course #{}".format(course_id))
  if not valid:
    return (
      False,
      "Couldn't find course #{}.".format(course_id)
    )
  tag = course_tag(course_id)

  # Check assignment name uniqueness:
  cur.execute(
    "SELECT id FROM assignments WHERE course_id = ? AND name = ?;",
    (course_id, assignment["name"])
  )
  if len(cur.fetchall()) > 0:
    return (
      False,
      "Assignment '{}' already exists in course {}.".format(
        assignment["name"],
        tag
      )
    )

  # create the assignment:
  cur.execute(
    "INSERT INTO assignments(course_id, name, flags, publish_at, due_at, late_after, reject_after, content) values(?, ?, ?, ?, ?, ?, ?, ?);",
    (
      course_id,
      assignment["name"],
      "list{" + ' '.join(assignment["flags"]) + "}",
      assignment["publish"].timestamp(),
      assignment["due"].timestamp(),
      assignment["late-after"].timestamp(),
      assignment["reject-after"].timestamp(),
      raw
    )
  )
  DBCON.commit()
  return (
    True,
    "Successfully created assignment '{}' for course {}.".format(
      assignment["name"],
      tag
    )
  )

def get_assignment_id(course_id, name):
  tag = course_tag(course_id)
  cur = DBCON.cursor()
  cur.execute(
    "SELECT id FROM assignments WHERE course_id = ? AND name = ?;",
    (course_id, name)
  )
  return unique_result_single(
    cur.fetchall(),
    "course #{} / assignment '{}'".format(course_id, name)
  )

def get_assignment_content(aid):
  cur = DBCON.cursor()
  cur.execute(
    "SELECT content FROM assignments WHERE id = ?;",
    (aid,)
  )
  content = unique_result_single(cur.fetchall(), "assignment #{}".format(aid))
  if not content:
    return (None, "Bad assignment id #{}.".format(aid))
  result = formats.parse_text(content)[0]
  valid, err = formats.process_assignment(result)
  if not valid:
    return (None, err)
  return (result, "Fetched assignment #{}.".format(aid))

def get_assignment_info(aid):
  cur = DBCON.cursor()
  cur.execute(
    "SELECT name, flags, publish_at, due_at, late_after, reject_after FROM assignments WHERE id = ?;",
    (aid,)
  )
  return unique_result(cur.fetchall(), "assignment #{}".format(aid))

def assignments_for(course_id, now, mode="all"):
  cur = DBCON.cursor()
  if mode == "current":
    cur.execute(
      "SELECT id FROM assignments WHERE course_id = ? AND publish_at <= ? AND reject_after >= ?;",
      (course_id, now, now)
    )
  elif mode == "future":
    cur.execute(
      "SELECT id FROM assignments WHERE course_id = ? AND reject_after >= ?;",
      (course_id, now)
    )
  else: # mode -> "all"
    cur.execute(
      "SELECT id FROM assignments WHERE course_id = ?;",
      (course_id,)
    )
  results = cur.fetchall()
  return [
    r["id"]
    for r in results
  ]

#########################
# Submission functions: #
#########################

def submit_assignment(user, aid, now, submission):
  assignment, msg = get_assignment_content(aid)
  if not assignment:
    return (False, msg)
  valid, err = formats.check_submission(assignment, submission)
  if err:
    return (False, err)
  raw = formats.unparse(submission)
  cur = DBCON.cursor()
  cur.execute(
    "INSERT INTO submissions(user, assignment_id, timestamp, content, feedback, grade) values(?, ?, ?, ?, ?, ?);",
    (user, aid, now, raw, "", None)
  )
  DBCON.commit()
  return (
    True,
    "Added new submission for assignment '{}' from user {}.".format(
      assignment["name"],
      user
    )
  )

def get_all_submissions_to(aid):
  cur = DBCON.cursor()
  cur.execute(
    "SELECT id, assignment_id, user, timestamp, content, feedback, grade FROM submissions WHERE assignment_id = ?;",
    (aid,)
  )
  return [SUB_F(*row) for row in cur.fetchall()]

def get_submissions_for(user, aid):
  cur = DBCON.cursor()
  cur.execute(
    "SELECT id, assignment_id, user, timestamp, content, feedback, grade FROM submissions WHERE user = ? AND assignment_id = ?;",
    (user, aid)
  )
  return [SUB_F(*row) for row in cur.fetchall()]


def get_rep_submissions_for(user, aid, now, finalized=True, any_late=False):
  cur = DBCON.cursor()
  cur.execute(
    "SELECT late_after, reject_after FROM assignments WHERE id = ?;",
    (aid,)
  )
  row = unique_result(cur.fetchall(), "assignment #{}".format(aid))
  if not row:
    return (None, None)

  late, reject = row

  submissions = get_submissions_for(user, aid)
  
  # update grade info proactively
  for sub in submissions:
    # ignore success/failure
    should, err = should_be_graded(sub, now)
    if err:
      print(err, file=sys.stderr)
    elif should:
      success, msg = set_grade_info(sub[0])
      if not success:
        print(msg, file=sys.stderr)

  submissions = get_submissions_for(user, aid)

  last_on_time = None
  last_late = None
  for sub in submissions:
    sid, aid, suser, stime, content, feedback, grade = sub
    if (
      stime <= late
    and (not finalized or now >= late)
    ):
      if last_on_time == None or stime > last_on_time.timestamp:
        last_on_time = sub
    if (
      stime > late
    and stime <= reject
    and (not finalized or any_late or now >= reject)
    ):
      if last_late == None or stime > last_late.timestamp:
        last_late = sub
  return last_on_time, last_late

######################
# Grading functions: #
######################

def grade_for(user, aid, now):
  cur = DBCON.cursor()
  cur.execute(
    "SELECT late_after, content FROM assignments WHERE id = ?;",
    (aid,)
  )
  row = unique_result(cur.fetchall(), "assignment #{}".format(aid))
  if not row:
    return (
      "Error: could not find assignment #{}.".format(aid),
      (
        None,
        "Error finding assignment for this submission."
      )
    )
  assignment = formats.parse_text(row["content"])[0]
  valid, err = formats.process_assignment(assignment)
  if not valid:
    return (err, (None, "Error: could not parse assignment from database."))

  if now < row["late_after"]: # before the true deadline
    return (
      "",
      (
        None,
        "Grades for assignment '{}' are not available until {} UTC.".format(
          assignment["name"],
          formats.date_string(formats.date_for(row["late_after"]))
        )
      )
    )

  # TODO: allow instructors to set late policies.
  late_policy = grading.flat_penalty_late_policy(0.5)
  last_ot, last_late = get_rep_submissions_for(
    user,
    aid,
    now,
    finalized = True,
    any_late = "grade-late-immediately" in assignment["flags"]
  )
  err, (grade, feedback) = grading.assignment_grade(
    assignment,
    row["late_after"],
    late_policy,
    # TODO: take multiple late submissions into account?
    (last_ot, last_late)
  )
  if err:
    return (err, (None, "Error: could not compute grade."))
  return ("", (grade, feedback))

def set_grade_info(sid):
  cur = DBCON.cursor()
  cur.execute(
    "SELECT user, assignment_id, content FROM submissions WHERE id = ?;",
    (sid,)
  )
  row = unique_result(cur.fetchall(), "submission #{}".format(sid))
  if not row:
    return (False, "Unknown submission #{}.".format(sid))

  assignment, msg = get_assignment_content(row["assignment_id"])
  if not assignment:
    return (False, "Couldn't find assignment #{}.".format(row["assignment_id"]))

  err, (grade, feedback) = grading.submission_grade(assignment, row)
  if err:
    return (False, err)

  cur.execute(
    "UPDATE submissions SET grade = ?, feedback = ? WHERE id = ?;",
    (grade, feedback, sid)
  )
  DBCON.commit()
  return (True, "Updated grade info for submission #{}.".format(sid))

def should_be_graded(submission, now):
  cur = DBCON.cursor()
  cur.execute(
    "SELECT id, flags, late_after, reject_after, content FROM assignments WHERE id = ?;",
    (submission.assignment_id,)
  );
  row = unique_result(
    cur.fetchall(),
    "assignment #{}".format(submission.assignment_id)
  )
  aid, flags, late_after, reject_after, content = row
  assignment = formats.parse_text(content)[0]
  valid, err = formats.process_assignment(assignment)
  if err:
    return (False, "Error checking assignment status: " + err)

  status = "unknown"
  if submission.timestamp <= late_after:
    status = "on-time"
  elif submission.timestamp <= reject_after:
    status = "late"
  else:
    status = "reject"

  if status == "unknown":
    return (
      False,
      "Error: unknown submission status for submission:\n{}".format(submission)
    )

  if (
    status == "on-time"
and (now >= late_after or "grade-immediately" in flags)
  ):
    return (True, "")

  if (
    status == "late"
and (
      now >= reject_after
   or "grade-immediately" in flags
   or "grade-late-immediately" in flags
    )
  ):
    return (True, "")

  if status == "reject":
    return (True, "")

  return (False, "")

def maintain_grade_info(last_ts, now):
  cur = DBCON.cursor()
  cur.execute(
    "SELECT id, assignment_id, user, timestamp, content, feedback, grade FROM submissions WHERE grade == ?;",
    (None,)
  )
  errors = []
  for row in cur.fetchall():
    should, err = should_be_graded(row, now)
    if err:
      errors.append(err)
    elif should:
      success, msg = set_grade_info(row[0])
      if not success:
        errors.append(
          "Error setting grade info for submission #{}:\n  {}".format(
            row[0],
            msg
          )
        )

  if errors:
    print("Errors while grading submissions:\n", file=sys.stderr)
    for e in errors:
      print("  " + e, file=sys.stderr)
  return None
