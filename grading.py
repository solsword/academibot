"""
grading.py
Grading functions.
"""

import formats

def flat_penalty_late_policy(late_value):
  return lambda x: (late_value if x > 0 else 1.0)

def correct_problems(asg, answers):
  valid, err = formats.check_submission(asg, answers)
  if not valid:
    return (err, [])
  return (
    "",
    [ p for p in asg["problems"] if answers[p["name"]] == p["solution"] ]
  )

def submission_grade(asg, sub):
  content = formats.parse_text(sub["content"])[0]
  err, correct = correct_problems(asg, content)
  if err:
    return (err, (None, "there was an error grading this submission"))
  cnames = [c["name"] for c in correct]
  incorrect = [p for p in asg["problems"] if p["name"] not in cnames]
  score = len(correct) / len(asg["problems"])
  return (
    "", # no error
    (
      score,
      "Correct: {}\nIncorrect: {}\n".format(
        ", ".join(c["name"] for c in correct) if correct else "<none>",
        ", ".join(i["name"] for i in incorrect) if incorrect else "<none>"
      )
    )
  )

def assignment_grade(asg, deadline, late_policy, submissions):
  best_scores = {}
  score_sources = {}
  score_status = {}
  for pn in [p["name"] for p in asg["problems"]]:
    best_scores[pn] = 0
    score_sources[pn] = "missing"
    score_status[pn] = "missing"
  for s in [x for x in submissions if x != None]:
    content = formats.parse_text(s.content)[0]
    err, correct = correct_problems(asg, content)
    if err:
      return (err, (None, "there was an error grading a submission"))
    cnames = [p["name"] for p in correct]
    credit = late_policy(s.timestamp - deadline)
    status = "on-time" if s.timestamp <= deadline else "late"
    for pn in [p["name"] for p in asg["problems"]]:
      if pn in cnames:
        if pn not in best_scores or credit > best_scores[pn]:
          best_scores[pn] = credit
          score_sources[pn] = s
          score_status[pn] = status
      else:
        if pn not in best_scores:
          best_scores[pn] = 0
          score_sources[pn] = s
          score_status[pn] = status

  feedback = "\n".join(
    "{}: {}{}".format(
      p["name"],
      "correct" if best_scores[p["name"]] > 0 else "incorrect",
      " ({})".format(score_status[p["name"]])
        if score_status[p["name"]] != "on-time"
        else ""
    ) for p in asg["problems"]
  )
  return (
    "",
    (
      sum(best_scores.values()) / len(asg["problems"]),
      feedback
    )
  )
