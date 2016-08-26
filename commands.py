"""
commands.py
academibot commands.
"""

import re

import storage

def parse(body):
  body = body.replace('\r', '')
  lines = body.split('\n')
  lines = [l.strip() for l in lines]
  for l in lines:
    if not l or l[0] == ">":
      continue
    words.extend(l.split())
  try:
    result = sort_commands(get_commands(words))
  except RecursionError:
    result = []
  return result

def sort_commands(cmds):
  result = []
  prioritized = []
  priorities = set()
  for (c, args) in cmds:
    p = COMMANDS[c]["priority"]
    priorities.add(p)
    prioritized.append((p, c, args))

  for pr in sorted(list(priorities)):
    for (p, c, args) in prioritized:
      if p == pr:
        result.append((c, args))

  return result

def get_commands(words):
  head, tail = words[0], words[1:]
  if head[0] == ":" and head[1:] in COMMANDS:
    args, rest = get_args(tail)
    return [(head[1:], args)] + get_commands(rest)
  else:
    return get_commands(tail)

def get_args(words):
  head, tail = words[0], words[1:]
  if head[0] == ":" and head[1:] in COMMANDS:
    return ([], words)
  else:
    args, rest = get_args(tail)
    return ([head] + args, rest)

def handle_commands(user, message, cmdlist):
  responses = []
  context = {
    "user": user,
    "message": message,
    "auth":
    {
      "users": [],
      "courses": [],
      "tokens": [],
    }
  }
  for (cmd, args) in cmdlist:
    result = COMMANDS[cmd]["run"](context, *args)
    responses.append("""\
Response for :{cmd}{args}
{result}
""".format(
  cmd = cmd,
  args = " " + " ".join(args) if args else "",
  result = result
))

  return (
    "Academibot reply.\n"
  + "="*80 + "\n"
  + ("\n" + "-"*80 + "\n").join(responses)
  )

def check_user_auth(context, user, action="perform that action"):
  """
  Returns an empty string if it succeeds or an error message if the current
  email isn't authorized for the given user. The message can be customized by
  providing the 'action' argument.
  """
  if user in context["auth"]["users"]:
    return ""
  else:
    return """\
Error: you need user authorization to {action}. Try again with the command:

:auth {user} <token>

(substituting the course's authorization token for <token>, of course)

Your user authentication token was sent to you when you first registered.
"""

def check_course_auth(context, course_id, action="access"):
  """
  Returns an empty string if it succeeds or an error message if the current
  email isn't authorized for the given course ID. The message can be customized
  by providing the 'action' argument.
  """
  if course_id in context["auth"]["courses"]:
    return ""
  else:
    return """\
Error: you need course authorization to {action} {course}. Try again with the command:

:auth {course} <token>

(substituting the course's authorization token for <token>, of course)

If you don't have an authorization token for this course, ask the person who created the course.
""".format(
  action=action,
  course=storage.course_tag(course_id)
)

def delegate(subcmd):
  result, msg = subcmd
  if result:
    return "Success: " + msg + "\n"
  else:
    return "Failure: " + msg + "\n"

def unpack_args(cmd, args, count, desc, mode="exact"):
  if len(args) < count:
    if count == 1:
      argreq = "one argument"
    else:
      argreq = "{} arguments".format(count)
    return (
      """
Error: Command :{cmd} requires at least {req}: {desc}

(command was parsed as: ":{cmd}{args}")
""".format(
  req=argreq,
  desc=desc,
  cmd = cmd,
  args = (" " + " ".join(args)) if args else ""
),
      (None,)*count
    )

  if mode == "all":
    return ("", args)
  else:
    return ("", args[:count])

def get_course(user, course):
  course_id = storage.get_course_id(user, course)
  if not course_id:
    return ("Error: course '{}' not found.\n".format(course), None, None)
  tag = storage.course_tag(course_id)
  return ("", course_id, tag)

#############
# Commands: #
#############

def cmd_help(context, *args):
  general = """\
To interact with academibot, send it an email containing one or more commands (each command should be on a separate line). Lines starting with '>' are ignored (so that it doesn't re-process commands in reply chains). Commands may take arguments, in which case they should come after the command on the same line, separated by spaces.
  
Academibot recognizes the following commands:

  {commandlist}
""".format(
  commandlist = "\n".join(
    "  :{cmd}{ad} -- {d}".format(
      cmd = c["name"],
      ad = " " + c["argdesc"] if c["argdesc"] else "",
      d = c["desc"]
    ) for c in sorted(COMMANDS.values(), key=labda c: c["name"])
  )
)
  body = ""
  if len(args) == 0:
    body = general
  else:
    cmd = args[0]
    if cmd in COMMANDS:
      body = COMMANDS[cmd]["help"]
    else:
      body = """\
Unknown command '{bad}'.

Full command was understood as:

:help {bad}

{general}
""".format(
  bad = cmd,
  general = general
)
  return body

def cmd_auth(context, *args):
  user = context["user"]
  err, (purpose, token) = unpack_args("auth", args, 2, "a purpose and a token")
  if err:
    return err
  if purpose[0] == "#":
    if storage.auth_token(user, purpose, token):
      context["auth"]["tokens"].append(purpose[1:])
      return "Authentication {} successful.\n".format(purpose)
    else:
      return "Invalid authentication for {}.\n".format(purpose)
  elif "@" in purpose:
    if storage.auth_user(purpose, token):
      context["auth"]["users"].append(purpose)
      return "Authentication as user '{}' successful.\n".format(purpose)
    else:
      return "Invalid authentication for user '{}'.\n".format(purpose)
  else:
    err, course_id, tag = get_course(user, purpose)
    if err:
      return """\
Error: unrecognized purpose '{}' for :auth.

(it did not start with '#' or contain '@' so it was assumed to be a course id, tag, or alias, but no matching course was found.)
""".format(purpose)
    if storage.auth_course(course_id, token):
      context["auth"]["courses"].append(course_id)
      return "Authentication for course '{}' succesful.\n".format(tag)
    else:
      return "Invalid authentication for course '{}'.\n".format(tag)

def cmd_scramble(context, *args):
  user = context["user"]
  err, (target,) = unpack_args("scramble", args, 1, "a user or course")
  if err:
    return err
  if '@' in target:
    if target in context["auth"]["users"] and target == user:
      token = storage.scramble_user(target)
      if not token:
        return "Error: ':scramble' could not find user '{}'.\n".format(user)
      else:
        return """\
Authentication for user '{user}' has been reset. The new token is:

{token}
""".format(user=target, token=token)

    elif target in context["auth"]["users"]:
      return """\
Error: to ':scramble' user '{}' you must send mail from the original account.
""".format(target)
    else:
      return "Error: you must authenticate to scramble user '{}'.\n".format(
        target
      )

  else:
    err, course_id, tag = get_course(user, target)
    if err:
      return err
    if target in context["auth"]["courses"]:
      token = storage.scramble_course(target)
      return """\
Authentication for course '{course}' has been reset. The new token is:

{token}
""".format(course=tag, token=token)
    else:
      return "Error: you must authenticate to scramble class '{}'.\n".format(
        tag
      )

def cmd_register(context, *args):
  user = context["user"]
  if storage.status(user) != "not-registered":
    return "User '{}' is already registered.\n".format(user)
  if "register" in context["auth"]["tokens"]:
    token = storage.add_user(user)
    return """
Successfully registered new user '{user}'.

Your authentication token is:

{token}

You will have to use this token to prove your identity for some commands by sending:

:auth {user} {token}
""".format(user=user, token=token)
  else:
    token = create_token(user, "register", duration=config.TEMP_AUTH_INTERVAL)
    return """\
Registration request acknowledged. Your temporary authentication token is {token} which is good for {duration} minutes. Please reply with the following commands to register:

:auth #register {token}
:register

Note that reply-quoted commands (anything on lines starting with '>') are ignored. If your authentication token times out, attempting to register will give you this message again.
""".format(
  token=token,
  duration=str(config.TEMP_AUTH_INTERVAL // 60)
)

def cmd_status(context, *args):
  user = context["user"]
  role = storage.role(user)
  status = storage.status(user)
  if status == "not-registered":
    return """\
User '{}' is not registered (send ":register" to register).
""".format(user, role, status)
  else:
    return """\
User '{}' has role '{}' and status '{}'
""".format(user, role, status)

def cmd_block(context, *args):
  user = context["user"]
  storage.set_block(user)
  return """\
You are now 'blocking' and will not receive any further messages or replies. Your commands will be ignored, except ':unblock' which will return you to active status.
"""

def cmd_unblock(context, *args):
  user = context["user"]
  storage.remove_block(user)
  return """\
You are now 'active' and can receive messages and send commands normally. Send the command ':block' to return to 'blocking' status.
"""

def cmd_expect(context, *args):
  user = context["user"]

  err, allargs = unpack_args(
    "expect",
    args,
    2,
    "a course and one or more students",
    mode="all"
  )
  if err:
    return err

  err, course_id, tag = get_course(user, allargs[0])
  if err:
    return err

  err = check_course_auth(context, course_id, "set expected students for")
  if err:
    return err

  # filter arguments:
  filtered = []
  for a in args:
    bits = a.split(',')
    for b in bits:
      st = b.strip()
      if st:
        filtered.append(st)

  results = []
  for f in filtered:
    status, message = storage.expect_student(course_id, f)
    results.append((f, status, message))

  attempted = len(results)
  succeeded = len(r for r in results if r[1])

  if succeeded > 0:
    tagline = "Successfully added {}/{} students".format(succeeded, attempted)
  else:
    tagline = "Failed to add any of {} students".format(attempted)

  return """\
{tagline} to the roster for course {tag}.

Results:
  {results}
""".format(
  tagline = tagline,
  tag = tag,
  results = "\n  ".join(
    "{} {} -- {}".format(" + " if r[1] else "***", r[0], r[2]) for r in results
  )
)

def cmd_enroll(context, *args):
  user = context["user"]
  err, (course,) = unpack_args("enroll", args, 1, "a course to enroll in")
  if err:
    return err

  err, course_id, tag = get_course(course)
  if err:
    return err

  delegate(storage.enroll_student(course_id, user))

def cmd_request(context, *args):
  user = context["user"]
  if len(args) < 2:
    return "Error: ':request' requires a type and a value.\n"

  typ = args[0]
  value = args[1]

  delegate(storage.submit_request(user, typ, value))

def cmd_grant(context, *args):
  user = context["user"]
  err, (target, typ, value) = unpack_args(
    "grant",
    args,
    3,
    "a user, a type, and a value"
  )
  if err:
    return err

  err = check_user_auth(context, user, "grant requests"):
  if err:
    return err

  # TODO: more granular permissions for various request types?
  if storage.role(user) != "admin":
    return """\
Error: only admins may grant requests. To request admin privileges send:

:request role admin
"""

  target = args[0]
  typ = args[1]
  value = args[2]

  delegate(storage.grant_request(target, typ, value))

def cmd_create_course(context, *args):
  user = context["user"]
  err, (institution, name, term, year) = unpack_args(
    "create_course"
    args,
    4,
    "four arguments (institution, course name, term, and year)"
  )
  if err:
    return err

  if any('@' in a or '/' in a for a in args[:4]):
    return "Error: '@' and '/' may not be used in institution names, course names, terms, or years.\n"

  err = check_user_auth(context, user, "create a course")
  if err:
    return err

  # TODO: role/perm free association system
  if storage.role(user) not in ["admin", "instructor"]:
    return """\
Error: to create a course you must be an instructor. To request instructor status send:

:request role instructor

An admin will need to approve your request.
"""

  delegate(storage.create_course(*args[:4]))

def cmd_add_instructor(context, *args):
  user = context["user"]
  err, (instructor, course) = unpack_args(
    "add_instructor",
    args,
    2,
    "a user and a course"
  )
  if err:
    return err

  err, course_id, tag = get_course(user, course)
  if err:
    return err

  err = check_course_auth(context, course_id, "add an instructor to")
  if err:
    return err

  delegate(storage.add_instructor(course_id, instructor))

def cmd_create_assignment(context, *args):
  user = context["user"]
  (
    err,
    (course, name, typ, value, publish, due, really_due, reject_after, _)
  ) = unpack_args(
    "create_assignment",
    args,
    9,
    "a course, an assignment name, an assignment type, a value, a publish date/time, a due date/time, a strict due date/time, a final submission date/time, and one or more problems"
  )
  problem_content = args[8:]

  err, course_id, tag = get_course(course)
  if err:
    return err

  err = check_course_auth(context, course_id, "create an assignment for")
  if err:
    return err

  # TODO: HERE

COMMANDS = {
  "help": {
    "name": "help",
    "run" : cmd_help,
    "priority": 10,
    "argdesc": "[command]",
    "desc": \
"Gives an explanation of [command], or general help if no [command] is given.",
    "help": """\
Help for command:
  :help

Usage examples:
  :help

  :help help

The help command. Replies with a general help message, or with help for a specific command if given as ":help <command>". For example you got this message because you sent a command ":help help". Note that the command name for the argument to help may not include the leading colon, or it will be interpreted as a command itself.
"""
  },
  "auth": {
    "name": "auth",
    "run" : cmd_auth,
    "priority": 1,
    "argdesc": "<purpose> <token>",
    "desc": "Authenticates for a particular purpose. User, course, and token authentication are supported.",
    "help": """\
Help for command:
  :auth

Usage examples:
  :auth test@example.com 15a0e830704e89a3c80b2c2995067241

  :auth example-college/test-course/winter/2035 cec46ec5145ab51eb92fafa418768686

  :auth #register fab9df15f2f0897f0043393c45326d10

Authenticates for a given purpose, enabling all commands in the same email requiring that specific privilege to function (:auth runs before other commands). You will receive an authentication token from academibot when you need one (for example, when you register you will receive a temporary token for registration, and then your permanent user token).
    
For user authentication, use your email as the <purpose>. To authenticate with a temporary token, use the token's purpose, preceded by a '#' sign (with no space in between). For course authentication, use either the numeric course ID, the full course tag (institution/course/term/year) or an alias that you have set up for that course.

You can use the ':scramble' command to reset permanent authentication tokens if you need to; temporary tokens can generally be re-requested by re-issuing the command that generated them.
"""
  },
  "scramble": {
    "name": "scramble",
    "run" : cmd_scramble,
    "priority": 100,
    "argdesc": "<entity>",
    "desc": "(requires authorization) Generates a new authentication token for the given user or course.",
    "help": """\
Help for command:
  :scramble

Usage examples:
  :auth test@example.com 15a0e830704e89a3c80b2c2995067241
  :scramble test@example.com

  :auth example-college/test-course/winter/2035 cec46ec5145ab51eb92fafa418768686
  :scramble example-college/test-course/winter/2035

Generates a fresh authentication token for the given user or course. Requires appropriate authorization (the old auth token). :scramble isn't run until after all other commands, so :auth commands using the old token will still work for the email in which :scramble is sent.
"""
  },
  "register": {
    "name": "register",
    "run" : cmd_register,
    "priority": 10,
    "argdesc": None,
    "desc": "(requires token) Registers the sender as a new user. Does nothing if already registered.",
    "help": """\
Help for command:
  :register

Usage examples:
  :register

  :auth #register 99dc985e08fcfb28382186ab8e3d6cc2
  :register

Registers the sender as a new user, which is required before enrolling in courses and submitting assignments. First use will generate a temporary authentication token in reply, which should be used with ':auth #register' and a second register command to actually register. Does nothing if the sender is already registered. Use :status to view role and status info.
"""
  },
  "status": {
    "name": "status",
    "priority": 10,
    "run" : cmd_status,
    "argdesc": None,
    "desc": \
"Responds with information about the sender's role and status.",
    "help": """\
Help for command:
  :status

Usage examples:
  :status

Responds with information about the sender's role and status. Roles give users special permissions (like the ability to create new courses and register students). Most users have the 'default' role. Statuses indicate whether a user is 'active,' or an 'alias.'
"""
  },
  "block": {
    "name": "block",
    "run" : cmd_block,
    "priority": 10,
    "argdesc": None,
    "desc": "Prevents the user from receiving any further mail. Commands except ':unblock' will be ignored",
    "help": """\
Help for command:
  :block

Usage examples:
  :block

Adds the sender to the 'blocking' list which prevents academibot from sending any mail to them and prevents academibot from processing their commands. The only exception to this is the ':unblock' command, which will remove them from the 'blocking' list. Commands sent in the same email as a ':block' or ':unblock' command will be processed normally and will generate responses. You can be on the 'blocking' list without being registered.
"""
  },
  "unblock": {
    "name": "unblock",
    "run" : cmd_unblock,
    "priority": 10,
    "argdesc": None,
    "desc": "Removes the user from the 'blocking' list, undoing a previous ':block' command.",
    "help": """\
Help for command:
  :unblock

Usage examples:
  :unblock

Reverses a previous ':block' command, removing the sender from the 'blocking' list. Commands sent in the same email as a ':block' or ':unblock' command will be processed normally and will generate responses. If ':block' and ':unblock' are sent in the same message, the final status of the sender depends on their order within the message, but all other commands in the message will be processed and generate responses regardless of their order in relation to the ':block' and ':unblock' commands. You can be on the 'blocking' list without being registered.
"""
  },
  "expect": {
    "name": "expect",
    "run" : cmd_expect,
    "priority": 10,
    "argdesc": "<course>, <user1>, <user2>, ...",
    "desc": "(requires auth) Takes a course followed by a list of email addresses and populates the expected roster for a course.",
    "help": """\
Help for command:
  :expect

Usage examples:
  :auth example-college/test-course/fall/2016 99dc985e08fcfb28382186ab8e3d6cc2
  :expect test-course test@example.com
    more@example.com
    with_commas@example.com,
    this_is_fine@example.com

For a user to enroll in a course, they must be expected. An instructor for the course should enter each student's email via this command before asking students to enroll in the course. Multiple emails can be entered across multiple lines, and commas are ignored. The first argument is the course in which to expect students; authorization for that course must be entered beforehand.
"""
  },
  "enroll": {
    "name": "enroll",
    "run" : cmd_enroll,
    "priority": 10,
    "argdesc": "<course>",
    "desc": "Takes a course and enrolls the sender in that course.",
    "help": """\
Help for command:
  :enroll

Usage examples:
  :enroll example-college/test-course/fall/2016

Enrolls the sender in the given course. Ask your instructor for the correct course ID or tag. You won't be able to enroll unless your instructor has already added you to the course roster, so if you get an error about unexpected enrollment, ask your instructor to add you  using the ':expect' command.
"""
  },
  "request": {
    "name": "request",
    "run" : cmd_request,
    "priority": 10,
    "argdesc": "<type> <value>",
    "desc": "Submits a permission request of the given type/value.",
    "help": """\
Help for command:
  :request

Usage examples:
  :request role instructor

Used to submit a request for a particular status or permission, which can then be granted by an admin using ':grant'. The ':grant' command may also happen before the ':request' command, in which case the change is pre-approved and takes place immediately.
"""
  },
  "grant": {
    "name": "grant",
    "run" : cmd_grant,
    "priority": 10,
    "argdesc": "<user> <type> <value>",
    "desc": "(requires auth) Grants the specified user's request of the given type/value.",
    "help": """\
Help for command:
  :grant

Usage examples:
  :auth admin@example.com a46590b7c08591b4b1a62417c8b68fe0
  :grant test@example.com role instructor

Grants a user's request. It requires user authorization from the granting party (the sender). Use ':requests' to view outstanding requests. ':grant' may also be used preemtively, in which case when a user submits a request, it will immediately be approved. Requests are one-time transactions: if a user requires multiple requests of the same type they must be granted permission multiple times.
"""
# TODO: log requests & permission changes
  },
  "create_course": {
    "name": "create_course",
    "run" : cmd_create_course,
    "priority": 10,
    "argdesc": "<institution> <name> <term> <year>",
    "desc": "(requires auth) Creates a new course, assigning the creator as an instructor.",
    "help": """\
Help for command:
  :create_course

Usage examples:
  :auth instructor@example.com c3ed3ab84e43f0c74a35b206ec43149a
  :create_course example-college test-course spring 1948

Creates a new course and assigns the creator as an instructor. It requires user authentication for the creator (the sender) who must be have either the 'admin' or 'instructor' role system-wide (this is different from being an instructor on a course). Note that none of the course elements may contain the '@' or '/' symbols.

The response to this command will include an authentication token for the new course, which the creator should keep track of.
"""
  },
  "add_instructor": {
    "name": "add_instructor",
    "run" : cmd_add_instructor,
    "priority": 10,
    "argdesc": "<user> <course>",
    "desc": "(requires auth) Adds the given user as an instructor for the given course.",
    "help": """\
Help for command:
  :add_instructor

Usage examples:
  :auth example-college/test-course/summer/2021 7b839a93c1012d2029cbe7d048716b34
  :add_instructor test@example.com example-college/test-course/summer/2021

Adds the given user as an instructor for the given course. Course-level authentication is required.
"""
  },
  "create_assignment": {
    "name": "create_assignment",
    "run" : cmd_create_assignment,
    "priority": 10,
    "argdesc": "<course> <name> <type> <value> <publish_at> <due_at> <really_due_at> <reject_after> <problem1> ...",
    "desc": "(requires auth) Creates a new assignment for the given course.",
    "help": """\
Help for command:
  :create_assignment

Usage examples:
  :auth example-college/test-course/spring/2150 846fc9b98ac4b5a859d5ded801154ce6
  :create_assignment
    example-college/test-course/spring/2150
  > the name of the new assignment:
    quiz-1
  > assignment type:
    quiz
  > assignment value (relative to all other assignments)
    1.0
  > This assignment will be published on January 25th at midnight (the beginning of the day, i.e., right after the end of January 24th):
    2150-1-25T00:00:00
  > It's due by the end of January 30th:
    2150-1-30T23:59:59
  > But submissions won't really be marked as late until 4:00 a.m. on January 31st:
    2150-1-31T04:00:00
  > Even late submissions won't be accepted after February 7th:
    2150-2-8T00:00:00
  > The rest of the arguments (everything up until the next command) define individual problems. Be careful not to include a valid command (a word starting with a ':') in any of the problem definitions. The problems are parsed as a series of 'problem{' blocks (see ':help problem{').
    problem{
      Name: 1
      Type: multiple-choice
      Flags: list{ randomize-order }
      Prompt: text{
        If two trains leave New York and Boston travelling towards each other, one going 30 km/h and the other travelling at 70 km/h, which train will reach the other first? }
      Answers: answers{
        ny: text{ The New York train. }
        bos: text{ The Boston train. }
        same: text{ They will reach each other at the same time. }
        sense: text{ This question doesn't make sense. }
      }
      Solution: same
    }
    problem{
      Name: text{ Problem 2 }
      Type: multiple-choice
      Prompt: text{ This is problem 2. Good luck. }
      Answers: answers{
        1: text { Um... }
        2: text { what? }
        3: text { This is not a good question. }
      }
      Solution: 3
    }


':create_assignment' creates a new assignment in the given course. It requires at least eight arguments:
    "argdesc": "<course> <name> <type> <value> <publish_at> <due_at> <really_due_at> <reject_after> <problem1> ...",
  1. The course to add the assignment to.
  2. The assignment name. Must be unique within a course.
  3. The assignment type. See ':help assignment-types'.
  4. The value of the assignment. Course grades are computed by summing the value of each assignment multiplied by the percentage score on that assignment, and are reported out of the total value of all assignments for a course.
  5. The date/time at which to publish the assignment. Times are given as YYYY-MM-DDTHH:MM:SS (see ':help time'). Before this time it won't be available to students.
  6. The date/time that the assignment is due as displayed to students.
  7. The actual date/time after which submissions will be marked as late. It's often a good idea to set this time several hours after the display deadline so that you don't have to field complaints and excuses about last-minute submissions.
  8. The date/time after which even late submissions won't be rejected. It's a good idea to be liberal with this, because making exceptions to this deadline is a pain. You can set up your late policy for a given assignment type to include a 0-credit deadline before the hard no-submissions deadline.
  9-... Further arguments are parsed as problems for the assignment.

Arguments past the 8th are parsed collectively as a sequence of problem definitions. ':help problem{' gives more information about how this format. Note that any valid academibot command will cut off the arguments of ':create_assignment', so commands cannot be included in problem definitions.
"""
  },
}

# TODO: Implement these!
FORMATS = {
  "problem": {
    "name": "problem",
    "desc": "Specifies a problem as part of an assignment."
    "help": """\
Help for format:
  text{

Usage examples:
  problem{
    Name: text{ Problem 1 }
    Type: multiple-choice
    Prompt: text{ What is your favorite color? }
    Answers: answers{
      1: Blue
      2: Green
      3: Grue
      4: text { I don't have a favorite color. }
    }
    Solution: 3
  }

The 'problem{' format... TODO: HERE

See also:
  :help answers{
  :help text{
"""
  }
  "answer": {
    "name": "answer",
    "desc": "Lists a set of answers to a problem."
    "help": """\
Help for format:
  answers{

Usage examples:
  answers{
    1: text{ Answer 1 }
    4: answer2
    three: text{ Names don't have to be numbers. }
    single-word: text{ But they must be single words. }
    2: text { Answer ordering is preserved regardless of names. }
  }

The 'answer{' format specifies a list of answers, each of which is indexed by a single word. TODO: HERE
"""
  }
  "text": {
    "name": "text",
    "desc": "Combines words into a single chunk of text."
    "help": """\
Help for format:
  text{

Usage examples:
  text{ This is some text that will be treated as a single token. }

  problem{
    Name: text{ A problem name with multiple words. }
    ...
  }

The 'text{' format combines all tokens until the matching '}' into a single chunk of text, which is then treated as a single token.
"""
  }
}
