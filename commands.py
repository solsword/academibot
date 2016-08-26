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

def check_user_auth(context, user, action="access"):
  """
  Returns an empty string if it succeeds or an error message if the current
  email isn't authorized for the given user. The message can be customized by
  providing the 'action' argument.
  """
  if user in context["auth"]["users"]:
    return ""
  else:
    return """\
Error: you need user authorization to {action} user '{user}'. Try again with the command:

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
    ) for c in COMMANDS.values()
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
  if len(args) < 2:
    return """
Error: :auth requires two arguments: a purpose and a token.

(command was parsed as: ":auth{}")
""".format(
  (" " + " ".join(args)) if args else ""
)
  purpose = args[0]
  token = args[1]
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
    course_id = storage.get_course_id(user, purpose)
    if not course_id:
      return """\
Error: unrecognized purpose '{}' for :auth.

(it did not start with '#' or contain '@' so it was assumed to be a course id, tag, or alias, but no matching course was found.)
""".format(purpose)
    tag = storage.course_tag(course_id)
    if storage.auth_course(course_id, token):
      context["auth"]["courses"].append(course_id)
      return "Authentication for course '{}' succesful.\n".format(tag)
    else:
      return "Invalid authentication for course '{}'.\n".format(tag)

def cmd_scramble(context, *args):
  user = context["user"]
  if len(args) < 1:
    return "Error: ':scramble' requires a user or course.\n"
  target = args[0]
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
      return "Error: you must authenticate to scramble user '{}'.".format(
        target
      )

  else:
    course_id = storage.get_course_id(user, target)
    tag = storage.course_tag(course_id)
    if not course_id:
      return "Error: ':scramble' could not find course '{}'.".format(target)
    if target in context["auth"]["courses"]:
      token = storage.scramble_course(target)
      return """\
Authentication for course '{course}' has been reset. The new token is:

{token}
""".format(course=tag, token=token)
    else:
      return "Error: you must authenticate to scramble class '{}'.".format(tag)

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

  if len(args) < 2:
    return "Error: ':expect' requires a course and one or more students."

  course = storage.get_course_id(user, args[0])
  if not course:
    return "Error: course '{}' not found.".format(args[0])
  tag = storage.course_tag(course_id)

  err = check_course_auth(context, course, "set expected students for")
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
{tagline} to the roster for class '{course}'.

Results:
  {results}
""".format(
  tagline = tagline,
  results = "\n  ".join(
    "{} {} -- {}".format(" + " if r[1] else "***", r[0], r[2]) for r in results
  )
)

def cmd_enroll(context, *args):
  user = context["user"]
  if len(args) < 1:
    return "Error: ':enroll' requires a course to enroll in."

  course = storage.get_course_id(user, args[0])
  if not course:
    return "Error: course '{}' not found.".format(args[0])

  result, message = storage.enroll_student(course_id, user)
  if result:
    return "Success: " + message
  else:
    return "Failure: " + message

def cmd_create_course(context, *args):
  # TODO: HERE

def cmd_add_instructor(context, *args):
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
}
