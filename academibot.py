#!/usr/bin/env python3
"""
academibotbot.py
Email bot for managing classes, including assignment submission, gradebook
management, and automatic grading.
"""

import async
import storage
import commands
import config

import getpass
import time

CON = None
SEND_QUEUE = []

def process(message):
  body = message["body"]
  user = message["from"] # TODO: better here!
  cmds = commands.parse(body)
  if storage.status(user) == "blocking":
    unblock = False
    for (c, args) in cmds:
      if c["name"] == "unblock":
        unblock = True
    if not unblock:
      return
  if cmds:
    response = commands.handle_commands(user, message, cmds)
    send_reply(message, response)

def send_reply(message, response):
  reply = {
    "to": [message["from"]],
    "subject": "Re: " + message["subject"],
    "body": response,
    "references": "{}{}".format(
      message["references"] + " " if message["references"] else "",
      message["mid"],
    ),
  }
  SEND_QUEUE.append(reply)

def flush_send_queue():
  global CON, SEND_QUEUE
  if len(SEND_QUEUE) == 0:
    return

  if not CON:
    CON = async.Connection(
      config.MYADDR,
      config.USERNAME,
      config.PASSWORD
    )

  CON.prepare_send()
  while len(SEND_QUEUE) > 0:
    CON.send_message(**SEND_QUEUE.pop())
  CON.done_sending()

def main():
  print("Starting academibot for:")
  print(config.MYADDR)
  config.PASSWORD = getpass.getpass(
    "Enter password for user '{}':".format(config.USERNAME)
  )
  print("...setting up storage...")
  storage.setup()
  print("...done...")
  try:
    CON = async.Connection(
      config.MYADDR,
      config.USERNAME,
      config.PASSWORD
    )
    while True:
      try:
        print("...cleaning auth tokens...")
        storage.clean_tokens()
        print("...checking mail...")
        CON.prepare_receive()
        messages = CON.check_mail()
        CON.done_receiving()
        print("...processing {} messages...".format(len(messages)))
        for m in messages:
          process(m)
        print("...sending {} responses...".format(len(SEND_QUEUE)))
        flush_send_queue()
        print("...done; sleeping for {} seconds...".format(config.INTERVAL))
        time.sleep(config.INTERVAL)
      except async.ConnectionError as e:
        print(e)
        print(
          "Connection error. Retrying next interval ({} seconds).".format(
            str(config.INTERVAL)
          )
        )
  except KeyboardInterrupt:
    pass
  print("Exiting academibot (incoming email will be ignored).")

if __name__ == "__main__":
  main()
