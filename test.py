#!/usr/bin/env python
"""
test.py
academibot unit tests. These tests use direct input with spoofed contexts
instead of actually using email input/output. Tests are run sequentially.
"""

import sys
import os

import academibot
import channel
import storage

TEST_INSTRUCTOR = "instructor@test.test"
TEST_STUDENTS = [
  "student1@test.test",
  "student2@test.test",
  "student3@test.test"
]
USER_TOKENS = {}
CLASS_TOKEN = None
CLASS_TAG = "UoT/test-theory/Spring/2017"

def get_auth_line(user):
  if user in USER_TOKENS:
    return ":auth {} {}\n".format(user, USER_TOKENS[user])
  else:
    return "> Auth token for user '{}' hasn't been created yet.".format(user)

def get_class_auth_line():
  if CLASS_TOKEN:
    return ":auth {} {}\n".format(CLASS_TAG, CLASS_TOKEN)
  else:
    return "> Auth token for '{}' hasn't been created yet.".format(CLASS_TAG)


class TestChannel (channel.Channel):
  def __init__(self, testcmds):
    self.cmds = testcmds
    self.next_cmds = []

  def add_cmd(self, user, send, respond):
    self.next_cmds.append((user, send, respond))

  def poll(self):
    result = []
    for user, send, respond in self.cmds:
      def modified_rf(response, myuser=user, myresponder=respond):
        myresponder(self.add_cmd, myuser, response)
      result.append(
        (user, send, modified_rf)
      )
    self.cmds = []
    return result

  def flush(self):
    self.cmds = self.next_cmds
    self.next_cmds = []
    if not self.cmds:
      print("Testing complete.")
      exit(0)

  def __str__(self):
    return "a test channel"

def continue_registration(further_tests=[]):
  def response_function(reply_function, sender, response):
    if "Registration request acknowledged" not in response:
      print("Error: ':register' message received invalid reply:")
      print(response)
      exit(1)
    grab = False
    reply = ""
    for line in response.split("\n"):
      if line.startswith(":auth"):
        reply += line + "\n"
        grab = True
        continue
      if grab:
        reply += line + "\n"
        break
    if not grab:
      print("Error: ':register' message received invalid reply.")
      print(response)
      exit(1)
    reply_function(sender, reply, complete_registration(further_tests))
  return response_function

def complete_registration(further_tests):
  def response_function(reply_function, sender, response):
    global USER_TOKENS
    if "Successfully registered new user '{user}'.".format(
      user=sender
    ) not in response:
      print("Error: authorized ':register' message received invalid reply.")
      print(response)
      exit(1)
    grab = 0
    for line in response.split("\n"):
      if line == "Your authentication token is:":
        grab = 1
        continue
      if grab == 1:
        grab = 2
        continue
      if grab == 2:
        grab = 3
        USER_TOKENS[sender] = line
        break
    if grab != 3:
      print("Error: authorized ':register' message received invalid reply.")
      print(response)
      exit(1)
    # Hack the test user into an admin role:
    # TODO: test :request and :grant
    if sender == TEST_INSTRUCTOR:
      storage.set_role(TEST_INSTRUCTOR, "instructor")
    for tsend, content, rf in further_tests:
      reply_function(
        tsend,
        content.format(
          uname=tsend,
          iname=TEST_INSTRUCTOR,
          sname1=TEST_STUDENTS[0],
          sname2=TEST_STUDENTS[1],
          sname3=TEST_STUDENTS[2],
          uauth=get_auth_line(tsend),
          iauth=get_auth_line(TEST_INSTRUCTOR),
          sauth1=get_auth_line(TEST_STUDENTS[0]),
          sauth2=get_auth_line(TEST_STUDENTS[1]),
          sauth3=get_auth_line(TEST_STUDENTS[2]),
          tag=CLASS_TAG,
          cauth=get_class_auth_line(),
        ),
        rf
      )
  return response_function

def post_course_creation(further_tests):
  def response_function(reply_function, sender, response):
    global CLASS_TOKEN
    if "Created course {ct} and added user '{user}'".format(
      ct=CLASS_TAG,
      user=sender
    ) not in response:
      print("Error: ':create-course' message received invalid reply.")
      print(response)
      exit(1)
    grab = 0
    for line in response.split("\n"):
      if "For course management, the authentication token is:" in line:
        grab = 1
        continue
      if grab == 1:
        grab = 2
        continue
      if grab == 2:
        grab = 3
        CLASS_TOKEN = line
        break
    if grab != 3:
      print("Error: ':create-course' message received malformed reply.")
      print(response)
      exit(1)
    for tsend, content, rf in further_tests:
      reply_function(
        tsend,
        content.format(
          uname=tsend,
          iname=TEST_INSTRUCTOR,
          sname1=TEST_STUDENTS[0],
          sname2=TEST_STUDENTS[1],
          sname3=TEST_STUDENTS[2],
          uauth=get_auth_line(tsend),
          iauth=get_auth_line(TEST_INSTRUCTOR),
          sauth1=get_auth_line(TEST_STUDENTS[0]),
          sauth2=get_auth_line(TEST_STUDENTS[1]),
          sauth3=get_auth_line(TEST_STUDENTS[2]),
          tag=CLASS_TAG,
          cauth=get_class_auth_line(),
        ),
        rf
      )
  return response_function

def check_and_chain(required, chain=[]):
  def response_function(reply_function, sender, response):
    for r in required:
      r = r.format(
          uname=sender,
          iname=TEST_INSTRUCTOR,
          sname1=TEST_STUDENTS[0],
          sname2=TEST_STUDENTS[1],
          sname3=TEST_STUDENTS[2],
          uauth=get_auth_line(sender),
          iauth=get_auth_line(TEST_INSTRUCTOR),
          sauth1=get_auth_line(TEST_STUDENTS[0]),
          sauth2=get_auth_line(TEST_STUDENTS[1]),
          sauth3=get_auth_line(TEST_STUDENTS[2]),
          tag=CLASS_TAG,
          cauth=get_class_auth_line(),
      )
      if r not in response:
        print("Error: received invalid reply.")
        print("Expected:\n{}\n".format(r))
        print("Recieved:\n{}\n".format(response))
        exit(1)
    for tsend, content, rf in chain:
      reply_function(
        tsend,
        content.format(
          uname=tsend,
          iname=TEST_INSTRUCTOR,
          sname1=TEST_STUDENTS[0],
          sname2=TEST_STUDENTS[1],
          sname3=TEST_STUDENTS[2],
          uauth=get_auth_line(tsend),
          iauth=get_auth_line(TEST_INSTRUCTOR),
          sauth1=get_auth_line(TEST_STUDENTS[0]),
          sauth2=get_auth_line(TEST_STUDENTS[1]),
          sauth3=get_auth_line(TEST_STUDENTS[2]),
          tag=CLASS_TAG,
          cauth=get_class_auth_line(),
        ),
        rf
      )
  return response_function

# Tests are given as [input, output]:


post_submit_tests = [
  (
    TEST_STUDENTS[0],
    """
    {uauth}
    :view-submissions {tag} quiz-1
    """,
    check_and_chain(
      [
        "Your latest submission for assignment 'quiz-1' in course {tag}:",
        "Submitted on time at ",
        "Content was:",
        "map{{ 1 : same text{{ Problem 2 }} : A }}",
        "Grade info not yet available",
      ]
    )
  ),
  (
    TEST_STUDENTS[0],
    """
    {uauth}
    :view-submissions {tag} quiz-2
    """,
    check_and_chain(
      [
        "Your latest submission for assignment 'quiz-2' in course {tag}:",
        "Submitted late at ",
        "Content was:",
        "map{{ 1 : same text{{ Problem 2 }} : A }}",
        "Grade: 100% Feedback: z",
      ]
    )
  ),
  (
    TEST_STUDENTS[1],
    """
    {uauth}
    :view-submissions {tag} quiz-1
    """,
    check_and_chain(
      [
        "You have not submitted assignment 'quiz-1' in course {tag}."
      ]
    )
  ),
  (
    TEST_INSTRUCTOR,
    """
    {cauth}
    :view-submissions {sname1} {tag} quiz-2
    """,
    check_and_chain(
      [
        "latest submission for assignment 'quiz-2' in course {tag}:",
        "Submitted late at ",
        "Content was:",
        "map{{ 1 : same text{{ Problem 2 }} : A }}",
      ]
    )
  ),
]

post_assignment_tests = [
  (
    TEST_INSTRUCTOR,
    """
    :list-assignments
    :assignment-status {tag} quiz-1
    """,
    check_and_chain(
      [
        "Assignment list:",
        "For course {tag}",
        "open",
        "Status for assignment 'quiz-1' in course {tag}:",
        "Grades for assignment 'quiz-1' are not available until 2016-12-31T12:00:00 UTC"
      ]
    )
  ),
  (
    TEST_INSTRUCTOR,
    """
    {cauth}
    :list-assignments
    :assignment-status {tag} quiz-1
    """,
    check_and_chain(
      [
        "Assignment list:",
        "For course {tag}",
        "open",
        "Status for assignment 'quiz-1' in course {tag}:",
        """\
Submissions summary ({stcount} students):
  on-time: {: 4d}
     late: {: 4d}
  revised: {: 4d}
  missing: {stcount: 4d}\
""".format(0, 0, 0, stcount=3)
      ]
    )
  ),
  (
    TEST_INSTRUCTOR,
    """
    :list-assignments {tag}
    """,
    check_and_chain(
      [
        "Assignment list:",
        "For course {tag}",
        "open",
      ]
    )
  ),
  (
    TEST_STUDENTS[0],
    """
    :list-assignments {tag}
    """,
    check_and_chain(
      [
        "Assignment list:",
        "For course {tag}",
        "open",
      ]
    )
  ),
  (
    TEST_STUDENTS[0],
    """
    {uauth}
    :view-submissions {tag} quiz-1
    """,
    check_and_chain(
      [
        "You have not submitted assignment 'quiz-1' in course {tag}."
      ]
    )
  ),
  (
    TEST_STUDENTS[0],
    """
    {uauth}
    :submit {tag} quiz-1
      map{{
        1 : same
        text{{ Problem 2 }} : A
      }}
    """,
    check_and_chain(
      [
        "Added new submission for assignment 'quiz-1' from user {uname}."
      ]
    )
  ),
  (
    TEST_STUDENTS[0],
    """
    {uauth}
    :submit {tag} quiz-2
      map{{
        1 : same
        text{{ Problem 2 }} : A
      }}
    """,
    check_and_chain(
      [
        "Added new submission for assignment 'quiz-2' from user {uname}."
      ],
      post_submit_tests
    )
  ),
  (
    TEST_STUDENTS[1],
    """
    :submit {tag} quiz-1
      map{{
        1 : ny
        text{{ Problem 2 }} : B
      }}
    """,
    check_and_chain(
      [
        "you need user authorization to submit assignments"
      ],
    )
  ),
]

post_enrolled_tests = [
  (
    TEST_INSTRUCTOR,
    """
    {cauth}
    :create-assignment 
      {tag}
      map{{
        name : quiz-1
        type : quiz
        value : 1.0
        flags : list{{ shuffle-problems }}
    > This assignment will be published on January 25th at midnight (the beginning of the day, i.e., right after the end of January 24th):
        publish : 2016-1-25T00:00:00
    > It's due by the end of December 30th:
        due : 2016-12-30T23:59:59
    > But submissions won't really be marked as late until 4:00 a.m. on December 31st:
        late-after : 2016-12-31T04:00:00
    > Even late submissions won't be accepted after January 7th:
        reject-after : 2017-1-7T00:00:00
    > The 'problems' value defines individual problems. Be careful not to include a valid command (a word starting with a ':') in any of the problem definitions. The problems are parsed as a 'list{{' of 'map{{' blocks (see ':help list' and ':help map').
        problems : list{{
          map{{
            name : 1
            type : multiple-choice
            flags : list{{ randomize-order }}
            prompt : text{{
              If two trains leave New York and Boston travelling towards each other, one going 30 km/h and the other travelling at 70 km/h, which train will reach the other first? }}
            answers : map{{
              ny : text{{ The New York train. }}
              bos : text{{ The Boston train. }}
              same : text{{ They will reach each other at the same time. }}
              sense : text{{ This question doesn't make sense. }}
            }}
            solution : same
          }}
          map{{
            name : text{{ Problem 2 }}
            type : multiple-choice
            prompt : text{{ This is problem 2. Good luck. }}
            answers : map{{
              A : text{{ Um... }}
              B : text{{ what? }}
              C : text{{ This is not a good question. }}
            }}
            solution : C
        }}
      }}
    }}
    """,
    check_and_chain(
      [
        "Successfully created assignment 'quiz-1' for course {tag}."
      ]
    )
  ),
  (
    TEST_INSTRUCTOR,
    """
    {cauth}
    :create-assignment 
      {tag}
      map{{
        name : quiz-2
        type : quiz
        value : 1.0
        flags : list{{ shuffle-problems }}
    > This assignment will be published on January 25th at midnight (the beginning of the day, i.e., right after the end of January 24th):
        publish : 2016-1-25T00:00:00
    > It's due by the end of January 30th:
        due : 2016-1-30T23:59:59
    > But submissions won't really be marked as late until 4:00 a.m. on January 31st:
        late-after : 2016-1-31T04:00:00
    > Even late submissions won't be accepted after January 7th:
        reject-after : 2017-1-7T00:00:00
    > The 'problems' value defines individual problems. Be careful not to include a valid command (a word starting with a ':') in any of the problem definitions. The problems are parsed as a 'list{{' of 'map{{' blocks (see ':help list' and ':help map').
        problems : list{{
          map{{
            name : 1
            type : multiple-choice
            flags : list{{ randomize-order }}
            prompt : text{{
              If two trains leave New York and Boston travelling towards each other, one going 30 km/h and the other travelling at 70 km/h, which train will reach the other first? }}
            answers : map{{
              ny : text{{ The New York train. }}
              bos : text{{ The Boston train. }}
              same : text{{ They will reach each other at the same time. }}
              sense : text{{ This question doesn't make sense. }}
            }}
            solution : same
          }}
          map{{
            name : text{{ Problem 2 }}
            type : multiple-choice
            prompt : text{{ This is problem 2. Good luck. }}
            answers : map{{
              A : text{{ Um... }}
              B : text{{ what? }}
              C : text{{ This is not a good question. }}
            }}
            solution : C
        }}
      }}
    }}
    """,
    check_and_chain(
      [
        "Successfully created assignment 'quiz-2' for course {tag}."
      ],
      post_assignment_tests
    )
  ),
]

# TODO: Should enrolling require user auth?
post_expected_tests = [
  (
    TEST_STUDENTS[0],
    """
    :enroll {tag}
    :enroll {tag}
    """,
    check_and_chain(
      [
        "Enrolled expected user '{uname}' in course",
        "User '{uname}' is already enrolled in course",
      ]
    )
  ),
  (
    TEST_STUDENTS[1],
    """
    :enroll {tag}
    """,
    check_and_chain(["Enrolled expected user '{uname}' in course"])
  ),
  ( # TODO: Check behavior for non-expected/-enrolled users
    TEST_STUDENTS[2],
    """
    :enroll {tag}
    """,
    check_and_chain(
      [
        "Enrolled expected user '{uname}' in course"
      ],
      post_enrolled_tests
    )
  ),
]

post_course_tests = [
  (
    TEST_STUDENTS[0],
    """
    :enroll {tag}
    """,
    check_and_chain(["User '{uname}' is not expected to enroll"])
  ),
  (
    TEST_STUDENTS[1],
    """
    :enroll {tag}
    """,
    check_and_chain(["User '{uname}' is not expected to enroll"])
  ),
  (
    TEST_INSTRUCTOR,
    """
    {cauth}
    :expect {tag} {sname1}
    """,
    check_and_chain(["Successfully added 1/1 students" ])
  ),
  (
    TEST_INSTRUCTOR,
    """
    {cauth}
    :expect {tag} {sname1} {sname2} {sname3}
    """,
    check_and_chain(
      [
        "User '{sname1}' is already expected for course",
        "Successfully added 2/3 students",
      ],
      post_expected_tests
    )
  ),
]

post_reg_tests = [
  (
    TEST_INSTRUCTOR,
    """
    {uauth}
    :create-course """ + ' '.join(CLASS_TAG.split('/')) + """
    """,
    post_course_creation(post_course_tests)
  ),
]

tests = [
  (
    TEST_INSTRUCTOR,
    """
    :help test
    """,
    check_and_chain(
      [
        "Unknown topic 'test'.",
        ":help test",
        "To interact with academibot"
      ]
    )
  ),
  (
    TEST_STUDENTS[0],
    """
    :register 
    """,
    continue_registration()
  ),
  (
    TEST_STUDENTS[1],
    """
    :register 
    """,
    continue_registration()
  ),
  (
    TEST_STUDENTS[2],
    """
    :register 
    """,
    continue_registration()
  ),
  (
    TEST_INSTRUCTOR,
    """
    :register 
    """,
    continue_registration(post_reg_tests)
  ),
]

if __name__ == "__main__":
  if os.path.exists("academibot-test.db"):
    os.remove("academibot-test.db")
  tc = TestChannel(tests)
  academibot.run_server(
    [tc],
    "academibot-test.db",
    0.01
  )
