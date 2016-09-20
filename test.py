"""
test.py
academibot unit tests. These tests use direct input with spoofed contexts
instead of actually using email input/output. Tests are run sequentially.
"""

import sys
import os

import academibot
import channel

TEST_USER = "tester@test.test"
USER_TOKEN = None
CLASS_TOKEN = None
CLASS_TAG = None

def get_auth_line():
  return ":auth {} {}\n".format(TEST_USER, USER_TOKEN)

def get_class_auth_line():
  return ":auth {} {}\n".format(CLASS_TAG, CLASS_TOKEN)


class TestChannel (channel.Channel):
  def __init__(self, testcmds):
    self.cmds = testcmds
    self.next_cmds = []

  def add_cmd(self, send, respond):
    self.next_cmds.append((send, respond))

  def poll(self):
    result = []
    for send, respond in self.cmds:
      def modified_rf(response, myresponder=respond):
        myresponder(self.add_cmd, response)
      result.append(
        (TEST_USER, send, modified_rf)
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

def check_response(expect=None, contains=None):
  def response_function(reply_function, response):
    error = False
    if expect:
      if response != expect:
        print(
          "Error: expected:\n  {}\n...but got:\n{}".format(expect, response),
          file=sys.stderr
        )
        error = True
    if contains:
      for c in contains:
        if c not in response:
          print(
            "Error: required content:\n  {}\n...was missing from:\n{}".format(
              c,
              response
            ),
            file=sys.stderr
          )
          error = True
    if error:
      exit(1)
    # reply_function is never called
    print("  ...check_response test succeeded...")
  return response_function

def continue_registration():
  def response_function(reply_function, response):
    print("CONTINUE REGISTRATION")
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
    reply_function(reply, complete_registration())
  return response_function

def complete_registration():
  def response_function(reply_function, response):
    global USER_TOKEN
    if "Successfully registered new user '{user}'.".format(
      user=TEST_USER
    ) not in response:
      print("Error: authorized ':register' message received invalid reply.")
      print(response)
      exit(1)
    grab = 0
    reply = ""
    for line in response.split("\n"):
      if line == "Your authentication token is:":
        grab = 1
        continue
      if grab == 1:
        grab = 2
        continue
      if grab == 2:
        grab = 3
        USER_TOKEN = line
        break
    if grab != 3:
      print("Error: authorized ':register' message received invalid reply.")
      print(response)
      exit(1)
    reply_function(reply, complete_registration())
    # TODO: Phase 2 tests
  return response_function

# Tests are given as [input, output]:
tests = [
  ("""
   :help test
   """,
   check_response(
     contains=[
       "Unknown topic 'test'.",
       ":help test",
       "To interact with academibot"
     ]
   )
  ),
  (
    """
    :register 
    """,
    continue_registration()
  )
]

round_2 = [
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
