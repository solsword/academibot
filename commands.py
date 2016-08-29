"""
commands.py
academibot commands.
"""

import collections
import datetime

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
  if head[0] == ':' and head[1:] in COMMANDS:
    args, rest = get_args(tail)
    return [(head[1:], args)] + get_commands(rest)
  else:
    return get_commands(tail)

def get_args(words):
  head, tail = words[0], words[1:]
  if head[0] == ":" and head[1:] in COMMANDS:
    return ([], words)
  elif head[-1] == '{' and head[:-1] in FORMATS:
    token, trest = FORMATS[head[:-1]]["parser"](tail)
    args, rest = get_args(trest)
    return ([token] + args, rest)
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

def parse_date(string):
  date_part, time_part = string.split('T')
  year, month, dat = date_part.split('-')
  hour, minute, second = time_part.split(':')
  try:
    dt = datetime.datetime(
      int(year),
      int(month),
      int(day),
      int(hour),
      int(minute),
      int(second),
      tzinfo=None
    )
  except ValueError:
    return None
  return dt

############
# Formats: #
############

def fmt_text(words, sofar=None):
  sofar = sofar or []
  head, tail = words[0], words[1:]
  if head == "}":
    return ' '.join(sofar), tail
  else:
    sofar.append(head)
    return fmt_text(tail, sofar)

def fmt_list(words, sofar=None):
  sofar = sofar or []
  head, tail = words[0], words[1:]
  if head[-1] == '{' and head[:-1] in FORMATS:
    token, trest = FORMATS[head[:-1]]["parser"](tail)
    sofar.append(token)
    return fmt_list(trest, sofar)
  elif head == "}":
    return sofar, tail
  else:
    sofar.append(head)
    return fmt_list(tail, sofar)

def fmt_map(words, key=None, sofar=None):
  sofar = sofar or collections.OrderedDict()
  head, tail = words[0], words[1:]
  if head[-1] == '{' and head[:-1] in FORMATS:
    token, trest = FORMATS[head[:-1]]["parser"](tail)
    if key:
      sofar[key] = token
      return fmt_map(trest, key=None, sofar=sofar)
    else:
      return fmt_map(trest, key=token, sofar=sofar)
  elif head == ":":
    if key:
      return fmt_map(tail, key=key, sofar=sofar)
    else:
      return fmt_map(tail, key=":", sofar=sofar)
  elif head == "}":
    return sofar, tail
  else:
    if key:
      sofar[key] = head
      return fmt_map(tail, key=None, sofar)
    else:
      return fmt_map(tail, key=head, sofar)

#############
# Commands: #
#############

def cmd_help(context, *args):
  general = """\
To interact with academibot, send it an email containing one or more commands (each command should be on a separate line). Lines starting with '>' are ignored (so that it doesn't re-process commands in reply chains). Commands may take arguments, in which case they should come after the command on the same line, separated by spaces.
  
Academibot recognizes the following commands:

  {commandlist}

Additionally, you can get help with these parsing formats:

  {formatlist}

Finally, there are some other general help topics:

  {topiclist}
""".format(
  commandlist = "\n".join(
    "  :{cmd}{ad} -- {d}".format(
      cmd = c["name"],
      ad = " " + c["argdesc"] if c["argdesc"] else "",
      d = c["desc"]
    ) for c in sorted(COMMANDS.values(), key=labda c: c["name"])
  ),
  formatlist = "\n".join(
    "  {fmt}{{ -- {d}".format(
      fmt = f["name"],
      d = f["desc"]
    ) for f in sorted(FORMATS.values(), key=labda f: f["name"])
  ),
  topiclist = "\n".join(
    "  {topic} -- {d}".format(
      topic = t["name"],
      d = t["desc"]
    ) for t in sorted(TOPICS.values(), key=labda t: t["name"])
  ),
)
  body = ""
  if len(args) == 0:
    body = general
  else:
    topic = args[0]
    if topic in COMMANDS:
      body = COMMANDS[topic]["help"]
    elif topic in FORMATS:
      body = FORMATS[topic]["help"]
    elif topic in TOPICS:
      body = TOPICS[topic]["help"]
    else:
      body = """\
Unknown topic '{bad}'.

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

  return delegate(storage.enroll_student(course_id, user))

def cmd_request(context, *args):
  user = context["user"]
  if len(args) < 2:
    return "Error: ':request' requires a type and a value.\n"

  typ = args[0]
  value = args[1]

  return delegate(storage.submit_request(user, typ, value))

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

  return delegate(storage.grant_request(target, typ, value))

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

  return delegate(storage.create_course(*args[:4]))

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

  return delegate(storage.add_instructor(course_id, instructor))

def cmd_create_assignment(context, *args):
  user = context["user"]
  ( err, (course, assignment) ) = unpack_args(
    "create_assignment",
    args,
    2,
    "a course and an assignment"
  )

  err, course_id, tag = get_course(course)
  if err:
    return err

  err = check_course_auth(context, course_id, "create an assignment for")
  if err:
    return err

  return delegate(storage.create_assignment(course_id, assignment))

FORMATS = {
  "text": {
    "name": "text",
    "parser": fmt_text,
    "desc": "Combines words into a single chunk of text."
    "help": """\
Help for format:
  text{

Usage examples:
  text{ This is some text that will be treated as a single token. }

  map{
    name : text{ A problem name with multiple words. }
    ...
  }

  text{ map{ these : tokens wont : be parsed : as a : map } }

The 'text{' format combines all tokens until the matching '}' into a single chunk of text, which is then treated as a single token. A single space is included between each sub-token, no matter how much whitespace separates them in the original text. Unlike other formats, the text{ format doesn't allow nested formats within it.
"""
  },
  "map": {
    "name": "map",
    "parser": fmt_map,
    "desc": "Lists a set of key <-> value relations."
    "help": """\
Help for format:
  map{

Usage examples:
  map{
    1 : text{ Value 1 }
    4 : value2
    three : text{ Names don't have to be numbers. }
    2 : text { Ordering is preserved regardless of names. }
    text{ A multi-word key } : text{ Keys must be single tokens. }
  }

  map{
    name : text{ Problem 1 }
    type : multiple-choice
    prompt : text{ What is your favorite color? }
    answers : map{
      1 : Blue
      2 : Green
      3 : Grue
      4 : text { I don't have a favorite color. }
    }
    solution : 3
  }

The 'map{' format specifies a list of key <-> value relations, where each key and value is a single token, and they are separated from each other by a ':' token (the ':' must be surrounded by spaces).

The 'map{' format is used for a couple of important purposes, including defining problems and their answers. See ':help problem"
"""
  },
  "list": {
    "name": "list",
    "parser": fmt_list,
    "desc": "Combines tokens into a list."
    "help": """\
Help for format:
  list{

Usage examples:
  list{ 1 2 3 4 5 }

  list{ flag-1 flag-2 other-flag }

The 'list{' format combines each of its sub-tokens into a single token which just contains a list of them. To treat multiple tokens as a single piece of text, use the 'text{' format instead.
"""
  },
}

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
    "argdesc": "<course> <assignment>",
    "desc": "(requires auth) Creates a new assignment for the given course.",
    "help": """\
Help for command:
  :create_assignment

Usage examples:
  :auth example-college/test-course/spring/2150 846fc9b98ac4b5a859d5ded801154ce6
  :create_assignment
    example-college/test-course/spring/2150
    map{
      name : quiz-1
      type : quiz
      value : 1.0
      flags : list{ shuffle-problems }
  > This assignment will be published on January 25th at midnight (the beginning of the day, i.e., right after the end of January 24th):
      publish : 2150-1-25T00:00:00
  > It's due by the end of January 30th:
      due : 2150-1-30T23:59:59
  > But submissions won't really be marked as late until 4:00 a.m. on January 31st:
      really-due : 2150-1-31T04:00:00
  > Even late submissions won't be accepted after February 7th:
      reject-after : 2150-2-8T00:00:00
  > The 'problems' value defines individual problems. Be careful not to include a valid command (a word starting with a ':') in any of the problem definitions. The problems are parsed as a 'list{' of 'map{' blocks (see ':help list' and ':help map').
      problems : list{
        map{
          name : 1
          type : multiple-choice
          flags : list{ randomize-order }
          prompt : text{
            If two trains leave New York and Boston travelling towards each other, one going 30 km/h and the other travelling at 70 km/h, which train will reach the other first? }
          answers : map{
            ny : text{ The New York train. }
            bos : text{ The Boston train. }
            same : text{ They will reach each other at the same time. }
            sense : text{ This question doesn't make sense. }
          }
          solution : same
        }
        map{
          name : text{ Problem 2 }
          type : multiple-choice
          prompt : text{ This is problem 2. Good luck. }
          answers : map{
            1 : text { Um... }
            2 : text { what? }
            3 : text { This is not a good question. }
          }
          solution : 3
        }
      }
    }


':create_assignment' creates a new assignment in the given course. It requires two arguments: a course ID, tag, or alias, and an assignment map. For the details of the format of the assignment map, see ':help assignment'. ':help problem' gives details on the format of individual problems.

Note that
"""
  },
}

TOPICS = {
  "assignment": {
    "name": "assignment",
    "desc": "The format for specifying an assignment.",
    "help": """\
Help for topic:
  assignment

Usage examples:
    map{
      name : quiz-1
      type : quiz
      value : 1.0
      flags : list{ shuffle-problems }
      publish : 2150-1-25T00:00:00
      due : 2150-1-30T23:59:59
      late-after : 2150-1-31T04:00:00
      reject-after : 2150-2-8T00:00:00
      problems : list{
        ...
      }
    }

    The create_assignment command requires an assignment map as an argument. The meaning of assignment keys is as follows:

  'name'
    Specifies the name of the assignment. This must be unique within a course, and is used by students when submitting the assignment, so it should be short and simple.

  'type'
    The assignment type. See ':help assignment-types' for details.

  'value'
    The value of the assignment. Course grades are computed by summing the value of each assignment multiplied by the percentage score on that assignment, and are reported out of the total value of all assignments for a course.

  'flags'
    This key is optional, and specifies special properties of the assignment. The following flags are recognized:
      'shuffle-problems' -- The problems will be presented in a different order for each student.

  'publish'
    The date/time at which to publish the assignment. Times are given as YYYY-MM-DDTHH:MM:SS (see ':help time'). Before this time it won't be available to students.

  'due'
    The public date/time that the assignment is due as displayed to students.

  'late-after'
    The actual date/time after which submissions will be marked as late. It's often a good idea to set this time several hours after the display deadline so that you don't have to field complaints and excuses about last-minute submissions.

  'reject-after'
    The date/time after which even late submissions won't be accepted. It's a good idea to be liberal with this, because making exceptions to this deadline is a pain (the bot won't accept or keep track of assignments past the reject-after time). You can set up your late policy for a given assignment type to include a 0-credit deadline before this hard reject-after deadline.

  'problems'
    The value for this key must be a list of 'problem' maps (see ':help list', ':help map', and ':help problem').

Note that any valid command will cut off the arguments of ':create_assignment', so commands cannot be included anywhere in assignment or problem definitions.
"""
  },
  "problem": {
    "name": "problem",
    "desc": "The format for specifying a problem within an assignment.",
    "help": """\
Help for topic:
  problem

Usage examples:
  map{
    name : text{ Problem 1 }
    type : multiple-choice
    flags : list{ number-answers shuffle-answers }
    prompt : text{ What is your favorite color? }
    answers : map{
      1 : Blue
      2 : Green
      3 : Grue
      4 : text { I don't have a favorite color. }
    }
    solution : 3
  }

The  'assignment' map format (see ':help assignment') includes a list of problems. Each problem is defined using a 'map{' block (see ':help map') that must include the following keys/values:

  'name'
    This key should have a 'text{' or single-word value that defines the name of the problem. Single-word values are preferable because students need to use this name as part of their assignment submissions.

  'type'
    This key defines the problem type. See ':help problem-types' for a list of recognized problem types.

  'flags'
    This key is optional, and defines special properties of the problem. The following flags are recognized:
      'number-answers' -- Use numbers instead of the given answer keys when presenting the answers.
      'shuffle-answers' -- When presenting the problem, the order of the answers will be different for each student.

  'prompt'
    This key should have a 'text{' value that describes the problem and asks a question. This content will be shown before the list of answers.

  'answers'
    The value of the 'type' key dictates what the 'answer' key should hold. See ':help problem-types'.

  'solution'
    The meaning of this field is also controlled by the 'type' value, but it generally indicates which answer is correct.
"""
  },
  "assignment-types": {
    "name": "assignment-types",
    "desc": "The valid assignment types and how they work.",
    "help": """\
Help for topic:
  assignment-types

Usage examples:
  :create_assignment
    example-college/test-course/spring/2150
    quiz-1
    quiz
    ...

The type argument to the ':create_assignment' command (see ':help create_assignment') specifies how the assignment is presented and managed. Valid types are:

  'quiz'
    A 'quiz' assignment just has a list of problems.
"""
  },
  "problem-types": {
    "name": "problem-types",
    "desc": "The valid problem types and how they work.",
    "help": """\
Help for topic:
  problem-types

Usage examples:
  map{
    ...
    type : multiple-choice
    ...
  }

The 'type' field of the 'problem' format specifies how the 'answers' and 'solution' fields are interpreted (see ':help problem'). Valid problem types are:

  'multiple-choice'
    A 'multiple-choice' type problem uses a 'map{' for its 'answers' value, where each value represents an exclusive choice, and there is a single correct answer. Accordingly, it's 'solution' value should be a single token which matches one of the keys of the 'answers' map and specifies which value is correct.
"""
  },
  "time": {
    "name": "time",
    "desc": "The format for specifying time values.",
    "help": """\
Help for topic:
  time

Usage examples:
  1970-1-1T00:00:00

  2016-08-30T18:00:00

  2042-12-30T23:59:59

  476-1-1T3:5:0

When a time value needs to be specified, such as the due date for an assignment, it takes the format: YYYY-MM-DDTHH:MM:SS, where the 'T' is a literal 'T' character but the rest of the letters stand for the year, month, day, hour, minute, and second of the specified time. Where a value would begin with a 0 it may omit the 0, although this is only recommended for month and day values.

Note that times are *always* understood in UTC, so you will have to figure out how your timezone and potentially daylight savings time differs from UTC. For example, a time given as:

  2016-8-30T18:00:00

would be eqivalent to 11:00 a.m. in Pacific Daylight Time, whereas

  2016-11-30T18:00:00

is still 11:00 a.m. PDT, but is also 10:00 a.m. Pacific Standard Time (which would be wall-clock time on the west coast of North America in November as opposed to August).

Allowing courses to specify a timezone (and daylight savings rules) is a feature in development.
"""
    # TODO: Get timzeone stuff working.
  },
}
