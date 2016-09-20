"""
formats.py
Special parsing and unparsing functions.
"""
import datetime
import collections

#####################
# Format functions: #
#####################

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

def date_for(timestamp):
  try:
    return datetime.utcfromtimestamp(timestamp)
  except ValueError:
    return None

def date_string(d):
  return d.strftime("%Y-%m-%dT%H:%M:%S")

def parse(words):
  if not words:
    return []
  head, tail = words[0], words[1:]
  if head[-1] == '{' and head[:-1] in FORMATS:
    token, leftover = FORMATS[head[:-1]]["parser"](tail)
    rest = parse(leftover)
    return [token] + rest
  else:
    rest = parse(tail)
    return [head] + rest

def unparse(structure, indent=0):
  """
  Note, unparse only handles string, list, dictionary, datetime, int, and float
  types. All other values are converted to strings using str().
  """
  ind = " " * indent
  t = type(structure)
  if t in (dict, collections.OrderedDict):
    result = ind + "map{\n" + "\n".join(
      (unparse(k, indent+2) + " :\n" + unparse(structure[k], indent+4))
      for k in structure
    ) + "\n" + ind + "}"
  elif t in (tuple, list):
    result = ind + "list{\n" + "\n".join(
      unparse(el, indent+2) for el in structure
    ) + "\n" + ind + "}"
  elif t == str:
    if ' ' in structure:
      result = ind + "text{\n"
      llen = 0
      for word in structure.split():
        nlen = llen + len(word) + 1
        if nlen > LINE_LENGTH:
          result += "\n" + ind + word
          llen = len(ind + word)
        else:
          result += " " + word
          llen += len(word) + 1
      result += "\n" + ind + "}"
    else:
      result = ind + structure
  elif t == datetime.datetime:
    result = ind + date_string(structure)
  elif t == float:
    result = ind + ("%.3f" % structure)
  else:
    result = ind + str(structure)
  oneliner = (" "*indent-1) + re.sub("^ *", " ", result).replace("\n", "")
  if len(oneliner <= LINE_LENGTH):
    return oneliner
  else:
    return result


def check_submission(assignment, submission):
  if type(submission) != dict:
    return (False, "Submission is not a map.")
  seen_answers = set()
  for key in submission:
    the_problem = None
    for p in assignment["problems"]:
      if p["name"] == key:
        the_problem = p
        if p["name"] in seen_answers:
          return (
            False,
            "Submission contains two answers for problem '{}'.".format(
              p["name"]
            )
          )
        seen_answers.add(p["name"])
        break

    if the_problem == None:
      return (
        False,
        "There is no problem '{}' in assignment '{}'.".format(
          key,
          assignment["name"]
        )
      )
    if submission[key] not in the_problem["answers"]:
      return (
        False,
        "Problem '{}' has no answer '{}'.".format(
          the_problem["name"],
          submission[key]
        )
      )

  missing = [p for p in assignment["problems"] if p["name"] not in seen_answers]

  minfo = ""
  if len(missing) > 2:
    minfo = "answers for problems {}, and {}".format(
      ", ".join("'{}'".format(m["name"]) for m in missing[:-1])
    )
  elif len(missing) == 2:
    minfo = "answers for problems '{}' and '{}'".format(minfo[0], minfo[1])
  elif len(missing) == 1:
    minfo = "the answer for problem '{}'".format(minfo[0])

  if minfo:
    return (
      False,
      "Submission is missing {}.".format(minfo)
    )

  return (True, "")


def check_problem(problem):
  for key in ("name", "type", "prompt", "answers", "solution"):
    if key not in problem:
      return (False, "Problem is missing required key '{}'.".format(key))
  if "flags" not in problem:
    problem["flags"] = []
  elif type(problem["flags"]) == str:
    problem["flags"] = problem["flags"].split()
  if type(problem["answers"]) != dict:
    return (False, "Answers must be a map.")
  if problem["solution"] not in problem["answers"]:
    return (False, "Solution doesn't match any of the answer keys.")
  return (True, "")

def process_assignment(assignment):
  for key in [
    "name", "type", "value", "publish", "due", "late-after", "reject-after",
    "problems"
  ]:
    if key not in assignment:
      return (False, "Assignment is missing required key '{}'.".format(key))
  if "flags" not in assignment:
    assignment["flags"] = []
  elif type(assignment["flags"]) == str:
    assignment["flags"] = assignment["flags"].split()
  try:
    fv = float(assignment["value"])
  except ValueError:
    return (
      False,
      "Invalid value field '{}' (could not be parsed as a number)".format(
        assignment["value"]
      )
    )
  assignment["value"] = fv
  for key in ("publish", "due", "late-after", "reject-after"):
    dt = commands.parse_date(assignment[key])
    if dt:
      assignment[key] = dt
    else:
      return (
        False,
        "Invalid {} value '{}' (could not be parsed as date/time).".format(
          key,
          assignment[key]
        )
      )
  used_names = set()
  for i, p in enumerate(assignment["problems"]):
    valid, err = check_problem(p)
    if not valid:
      return (False, "Error with problem #{}:\n".format(i+1) + err)
    if p["name"] in used_names:
      return (
        False,
        "Problem #{} repeats the use of name '{}'.".format(i+1, p["name"])
      )
    used_names.add(p["name"])
  return (True, "")


###################
# Format parsers: #
###################

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
      return fmt_map(tail, key=None, sofar=sofar)
    else:
      return fmt_map(tail, key=head, sofar=sofar)

#######################
# Format definitions: #
#######################

FORMATS = {
  "text": {
    "name": "text",
    "parser": fmt_text,
    "desc": "Combines words into a single chunk of text.",
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
  "list": {
    "name": "list",
    "parser": fmt_list,
    "desc": "Combines tokens into a list.",
    "help": """\
Help for format:
  list{

Usage examples:
  list{ 1 2 3 4 5 }

  list{ flag-1 flag-2 other-flag }

The 'list{' format combines each of its sub-tokens into a single token which just contains a list of them. To treat multiple tokens as a single piece of text, use the 'text{' format instead.
"""
  },
  "map": {
    "name": "map",
    "parser": fmt_map,
    "desc": "Lists a set of key <-> value relations.",
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
}
