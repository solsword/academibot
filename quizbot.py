#!/usr/bin/env python3
"""
quizbot.py
Bot that responds to email commands and administers quizzes.
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
  cmds = commands.parse(body)
  if cmds:
    response = commands.handle_commands(cmds)
    send_reply(message, response)

def send_reply(message, response):
  reply = {
    "to": [message["from"]],
    "subject": "Re: " + message["subject"],
    "body": response,
    "references": "{}{}".format(
      message["references"] + " " if message["references"] else "",
      str(message["uid"]),
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
  print("Starting quizbot for:")
  print(config.MYADDR)
  config.PASSWORD = getpass.getpass(
    "Enter password for user '{}':".format(config.USERNAME)
  )
  try:
    CON = async.Connection(
      config.MYADDR,
      config.USERNAME,
      config.PASSWORD
    )
    while True:
      try:
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
  print("Exiting quizbot (incoming email will be ignored).")

if __name__ == "__main__":
  main()
