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
import traceback
import sys

import time

CONTEXT = "unknown"

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
    response = commands.handle_commands(sender, body, cmds, now)
    reply_function(response)

def run_server(channels, db_name="academibot.db", interval=10):
  global CONTEXT
  print("Starting academibot with channels:")
  sys.stdout.flush()
  for c in channels:
    print("  ..." + str(c) + "...")
  sys.stdout.flush()
  print("...setting up storage...")
  storage.setup(db_name)
  sys.stdout.flush()
  print("...setting up channels...")
  for c in channels:
    c.setup()
  sys.stdout.flush()
  print("...done...")
  sys.stdout.flush()
  try:
    now = 0
    last = 0
    while True:
      last = now
      now = storage.now_ts()
      try:
        CONTEXT = "...cleaning auth tokens..."
        storage.clean_tokens()
        CONTEXT = "...auto-grading..."
        err = storage.maintain_grade_info(last, now)
        if err:
          print("Error while...")
          print(CONTEXT)
          print(err)
          print("  ...ignoring error...")
          sys.stdout.flush()
          sys.stderr.flush()
        CONTEXT = "...checking channels..."
        messages = []
        for c in channels:
          messages.extend(c.poll())
        CONTEXT = "...processing {} messages...".format(len(messages))
        for sender, body, rf in messages:
          try:
            process(sender, body, rf, now)
          except Exception as e:
            print("Error while...")
            print(CONTEXT)
            #print(e)
            traceback.print_exc()
            print("...error processing message; reporting to user...")
            rf(
                """
Academibot encountered an error while trying to to process your message.

Please either re-send your message with different data or try to contact an
instructor about what you should do.
"""
            )
            print("...done reporting; ignoring message...")
            sys.stdout.flush()
            sys.stderr.flush()
        CONTEXT = "...flushing channels..."
        for c in channels:
          c.flush()
        CONTEXT = "...done; sleeping for {} seconds...".format(interval)
        time.sleep(interval)
      except Exception as e:
        if type(e) == KeyboardInterrupt:
          print("During...")
          print(CONTEXT)
          sys.stdout.flush()
          sys.stderr.flush()
          raise e
        print("Error while...")
        print(CONTEXT)
        print(e)
        traceback.print_exc()
        print(
          "Processing error. Retrying next interval ({} seconds).".format(
            str(interval)
          )
        )
        sys.stdout.flush()
        sys.stderr.flush()
        time.sleep(interval)
  except KeyboardInterrupt:
    pass
  print("Exiting academibot (incoming email will be ignored).")
  sys.stdout.flush()
  sys.stderr.flush()

def main():
  run_server(
    [
      mail.AsyncEmailChannel(
        config.NAME,
        config.MYADDR,
        config.IMAP_USERNAME,
        config.SMTP_USERNAME
      )
    ],
    config.DATABASE,
    interval=config.INTERVAL
  )

if __name__ == "__main__":
  main()
