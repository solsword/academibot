#!/usr/bin/env python3
"""
academibotbot.py
Email bot for managing classes, including assignment submission, gradebook
management, and automatic grading.
"""

import mail
import storage
import commands
import config

import time

CON = None
SEND_QUEUE = []

def process(sender, body, reply_function, now):
  cmds = commands.parse(body)
  if storage.status(sender) == "blocking":
    unblock = False
    for (c, args) in cmds:
      if c["name"] == "unblock":
        unblock = True
    if not unblock:
      return
  if cmds:
    response = commands.handle_commands(sender, message, cmds, now)
    reply_function(response)

def run_server(channels):
  print("Starting academibot with channels:")
  for c in channels:
    print("  ..." + str(c) + "...")
  print("...setting up storage...")
  storage.setup()
  print("...setting up channels...")
  for c in channels:
    c.setup()
  print("...done...")
  try:
    now = 0
    last = 0
    while True:
      last = now
      now = storage.now_ts()
      try:
        print("...cleaning auth tokens...")
        storage.clean_tokens()
        print("...auto-grading...")
        storage.maintain_grade_info(last, now)
        print("...checking channels...")
        messages = []
        for c in channels:
          messages.extend(c.poll())
        print("...processing {} messages...".format(len(messages)))
        for sender, body, rf in messages:
          try:
            process(sender, body, rf, now)
          except Exception as e:
            print(e)
            print("...error processing message; ignoring...")
        print("...flushing channels...")
        for c in channels:
          c.flush()
        print("...done; sleeping for {} seconds...".format(config.INTERVAL))
        time.sleep(config.INTERVAL)
      except Exception as e:
        if type(e) == KeyboardInterrupt:
          raise e
        print(e)
        print(
          "Processing error. Retrying next interval ({} seconds).".format(
            str(config.INTERVAL)
          )
        )
        time.sleep(config.INTERVAL)
  except KeyboardInterrupt:
    pass
  print("Exiting academibot (incoming email will be ignored).")

def main():
  run_server(
    [mail.AsyncEmailChannel(config.MYADDR, config.USERNAME)]
  )

if __name__ == "__main__":
  main()
