#!/usr/bin/env python3
import smtplib
import imaplib
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import mimetypes
import getpass
import html.parser

import config
import channel

"""
mail.py
Asyncrhonous email checking via IMAP4 (receive) and SMTP (send).

Roughly based on:
https://github.com/jayrambhia/Basic-Gmail-API/blob/master/Basic-gmail.py
"""

class ConnectionError(RuntimeError):
  pass

class Connection:
  def __init__(
    self,
    name,
    address,
    imap_username,
    smtp_username,
    imap_password,
    smtp_password
  ):
    self.name = name
    self.address = address
    self.imap_username = imap_username
    self.smtp_username = smtp_username
    self.imap_password = imap_password
    self.smtp_password = smtp_password
    self.smtp_server = None
    self.imap_server = None

  def connect_smtp(self):
    if (self.smtp_server != None):
      raise ConnectionError("Attempt to connect SMTP while already connected.")
    self.smtp_server = smtplib.SMTP()
    self.smtp_server.connect(config.SMTP_HOST, config.SMTP_PORT)
    self.smtp_server.ehlo()
    self.smtp_server.starttls()
    self.smtp_server.ehlo()
    self.smtp_server.login(self.smtp_username, self.smtp_password)

  def disconnect_smtp(self):
    self.smtp_server.quit()
    self.smtp_server = None

  def connect_imap(self):
    if (self.imap_server != None):
      raise ConnectionError("Attempt to connect IMAP while already connected.")
    self.imap_server = imaplib.IMAP4_SSL(config.IMAP_HOST, config.IMAP_PORT)
    self.imap_server.login(self.imap_username, self.imap_password)

  def disconnect_imap(self):
    self.imap_server.logout()
    self.imap_server = None

  def prepare_send(self):
    if self.smtp_server == None:
      self.connect_smtp()

  def done_sending(self):
    if self.smtp_server != None:
      self.disconnect_smtp()

  def prepare_receive(self):
    if self.imap_server == None:
      self.connect_imap()

  def done_receiving(self):
    if self.imap_server != None:
      self.disconnect_imap()

  def send_message(
    self,
    to = None,
    subject = "ERROR",
    body = "ERROR -- send_message didn't get a 'body' argument.",
    references = "",
    attachments = None
  ):
    if to == None:
      raise ConnectionError(
        "Connection.send_message didn't get a list of recipients."
      )

    attachments = attachments or []
    msg = MIMEMultipart()
    msg["From"] = self.address
    msg["To"] = email.utils.COMMASPACE.join(to)
    msg["Subject"] = "{" + self.name + "} " + subject
    msg["References"] = references
    if body:
      msg.attach(MIMEText(body))
    for a in attachments:
      msg.attach(a)
    msg.attach(
      MIMEText(
        """
This is an automated message sent by {address}.

To halt all further messages from {address}, reply with the text ":block"
""".format(address = self.address)
      )
    )
    self.smtp_server.sendmail(self.address, to, msg.as_string())

  def check_mail(self):
    #status, boxnames = self.imap_server.list()
    #if status != "OK":
    #  raise ConnectionError("IMAP list() returned bad status '%s'" % status)
    #boxes = [bn.split('"')[-2] for bn in boxnames]
    status, mcount = self.imap_server.select("INBOX")
    if status != "OK":
      raise ConnectionError("IMAP select() returned bad status '%s'" % status)
    status, data = self.imap_server.uid("search", None, "UNSEEN")
    if status != "OK":
      raise ConnectionError(
        "IMAP uid('search') returned bad status '%s'" % status
      )
    uid_list = data[0].split()
    messages = []
    for uid in uid_list:
      status, data = self.imap_server.uid('fetch', uid, "(RFC822)")
      if status != "OK":
        raise ConnectionError(
          "IMAP uid('fetch') returned bad status '%s'" % status
        )
      raw = data[0][1]
      msg = email.message_from_bytes(raw)
      messages.append(
        {
          'uid': uid,
          'mid': msg["Message-Id"] if "Message-Id" in msg else "?",
          'from': email.utils.parseaddr(msg["From"])[1],
          'subject': msg["Subject"],
          'references': msg["References"],
          'body': self.get_body(msg),
        }
      )
    self.imap_server.close()
    return messages

  def get_body(self, message):
    body = ""
    for part in message.walk():
      content_type = part.get_content_type()
      if content_type == "text/plain":
        payload = part.get_payload()
        if payload:
          body += payload
      #elif content_type == "text/html":
      #  payload = part.get_payload()
      #  if payload:
      #    body += payload
    return body

class AsyncEmailChannel(channel.Channel):
  def __init__(self, name, myaddr, imap_username, smtp_username, samepass=True):
    self.name = name
    self.addr = myaddr
    self.imap_username = imap_username
    self.smtp_username = smtp_username
    self.imap_password = None
    self.smtp_password = None
    self.connection = None
    self.outbound = []
    self.samepass = samepass

  def __str__(self):
    return "an asynchronous email channel via {}".format(self.addr)

  def setup(self):
    # TODO: don't store password even in RAM? (in Connection as well)
    if self.samepass:
      self.imap_password = getpass.getpass(
        "Enter password for user '{}':".format(self.imap_username)
      )
      self.smtp_password = self.imap_password
    else:
      self.imap_password = getpass.getpass(
        "Enter password for IMAP user '{}':".format(self.imap_username)
      )
      self.smtp_password = getpass.getpass(
        "Enter password for SMTP user '{}':".format(self.smtp_username)
      )
    self.connection = Connection(
      self.name,
      self.addr,
      self.imap_username,
      self.smtp_username,
      self.imap_password,
      self.smtp_password
    )

  def poll(self):
    self.connection.prepare_receive()
    messages = self.connection.check_mail()
    self.connection.done_receiving()
    return [
      (
        m["from"], # TODO: Better sender authentication!
        m["body"],
        self.respond_function_for(m)
      )
      for m in messages
    ]

  def respond_function_for(self, message):
    def rf(response_text):
      reply = {
        "to": [message["from"]],
        "subject": "Re: " + message["subject"],
        "body": response_text,
        "references": "{}{}".format(
          message["references"] + " " if message["references"] else "",
          message["mid"],
        ),
      }
      self.outbound.append(reply)
    return rf

  def flush(self):
    if len(self.outbound) == 0:
      return

    if not self.connection:
      self.connection = Connection(
        self.addr,
        self.imap_username,
        self.smtp_username,
        self.imap_password,
        self.smtp_password
      )

    self.connection.prepare_send()
    while len(self.outbound) > 0:
      self.connection.send_message(**self.outbound.pop())
    self.connection.done_sending()

def test_message():
  con = Connection(
    config.NAME,
    config.MYADDR,
    config.USERNAME,
    getpass("Password for {}".format(config.USERNAME))
  )
  con.connect_smtp()
  tolist = [ "pmawhorter@gmail.com" ]
  subject = "Test Email"
  body = "Test email body"
  con.send_message(tolist, subject, body)
  con.disconnect_smtp()

if __name__ == "__main__":
  test_message();
