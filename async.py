#!/usr/bin/env python3
import smtplib
import imaplib
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import mimetypes

import config

"""
async.py
Asyncrhonous email checking via IMAP4 (receive) and SMTP (send).

Roughly based on:
https://github.com/jayrambhia/Basic-Gmail-API/blob/master/Basic-gmail.py
"""

class ConnectionError(RuntimeError):
  pass

class Connection:
  def __init__(self, address, username, password):
    self.address = address
    self.username = username
    self.password = password
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
    self.smtp_server.login(self.username, self.password)

  def disconnect_smtp(self):
    self.smtp_server.quit()
    self.smtp_server = None

  def connect_imap(self):
    if (self.imap_server != None):
      raise ConnectionError("Attempt to connect IMAP while already connected.")
    self.imap_server = imaplib.IMAP4_SSL(config.IMAP_HOST)
    self.imap_server.login(self.username, self.password)

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
    msg["Subject"] = "{quizbot} " + subject
    msg["References"] = references
    if body:
      msg.attach(MIMEText(body))
    for a in attachments:
      msg.attach(a)
    msg.attach(
      MIMEText(
        "This is an automated message sent by quizbot.email@gmail.com."
      )
    )
    self.smtp_server.sendmail(self.username, to, msg.as_string())

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
      if content_type == "text/plain" or content_type == "text/html":
        payload = part.get_payload()
        if payload:
          body += payload
    return body

def test_message():
  con = Connection(
    MYADDR,
    USERNAME,
    getpass("Password for {}".format(USERNAME))
  )
  con.connect_smtp()
  tolist = [ "pmawhorter@gmail.com" ]
  subject = "Test Email"
  body = "Test email body"
  con.send_message(tolist, subject, body)
  con.disconnect_smtp()

if __name__ == "__main__":
  test_message();
