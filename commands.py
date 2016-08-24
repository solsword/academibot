"""
commands.py
Quizbot commands.
"""

import re

import storage

def parse(body):
  body = body.replace('\r', '')
  lines = body.split('\n')
  lines = [l.strip() for l in lines]
  found = []
  for l in lines:
    if not l or l[0] == ">":
      continue

    words = l.split()
    for c in COMMANDS.values():
      cw = "quizbot:" + c["name"]
      if cw in words:
        i = words.index(cw)
        if c["args"]:
          args = words[i+1:]
        else:
          args = []
        found.append((c, args))
  return found

def handle_commands(message, cmdlist):
  responses = []
  for (cmd, args) in cmdlist:
    responses.append("""\
Response for quizbot:{cmd}{args}
{result}
""".format(
  cmd = cmd["name"],
  args = " " + " ".join(args) if args else "",
  result = cmd["run"](message, *args)
))

  return "Quizbot reply.\n---\n" + "\n---\n".join(responses)

def cmd_help(message, *args):
  general = """\
To interact with quizbot, send it an email containing one or more commands (each command should be on a separate line). Lines starting with '>' are ignored (so that it doesn't re-process commands in reply chains). Commands may take arguments, in which case they should come after the command on the same line, separated by spaces.
  
Quizbot recognizes the following commands:

  {commandlist}
""".format(
  commandlist = "\n".join(
    "  quizbot:{cmd}{ad} -- {d}".format(
      cmd = c["name"],
      ad = " " + c["argdesc"] if c["args"] else "",
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

quizbot:help {bad}

{general}
""".format(
  bad = cmd,
  general = general
)
  return body

def cmd_register(message, *args):
  user = message["from"]
  if storage.status(user) != "not-registered":
    return "User '{}' is already registered.".format(user)
  storage.add_user(user)
  return "Successfully registered user '{}'".format(user)

def cmd_status(message, *args):
  user = message["from"]
  role = storage.role(user)
  status = storage.status(user)
  if status == "not-registered":
    return """\
User '{}' is not registered (send "quizbot:register" to register).\
""".format(user, role, status)
  else:
    return """\
User '{}' has role '{}' and status '{}'\
""".format(user, role, status)

COMMANDS = {
  "help": {
    "name": "help",
    "args": True,
    "run" : cmd_help,
    "argdesc": "<command>",
    "desc": \
"Gives an explanation of <command>, or general help if no <command> is given.",
    "help": """\
Help for command:
  quizbot:help

The help command. Replies with a general help message, or with help for a specific command if given as "quizbot:help <command>". For example you got this message because you sent a command "quizbot:help help".
"""
  },
  "register": {
    "name": "register",
    "args": False,
    "run" : cmd_register,
    "desc": \
"Registers the sender as a new user. Does nothing if already registered.",
    "help": """\
Help for command:
  quizbot:register

Registers the sender as a new user, which is required before enrolling in classes and submitting assignments. Does nothing if the sender is already registered. Use quizbot:status to view role and status info.
"""
  },
  "status": {
    "name": "status",
    "args": False,
    "run" : cmd_status,
    "desc": \
"Responds with information about the sender's role and status.",
    "help": """\
Help for command:
  quizbot:status

Responds with information about the sender's role and status. Roles give users special permissions (like the ability to create new classes and register students). Most users have the 'default' role. Statuses indicate whether a user is 'active,' or 'blocking.' No email will be sent to users who are 'blocking,' and commands from such users will be ignored, except the 'unblock' command.
"""
  },
}
