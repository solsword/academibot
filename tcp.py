"""
tcp.py
A TCP channel for academibot based on asyncio.
"""

import asyncio

import channel

class TCPChannel (channel.Channel):
  def __init__(self, address="127.0.0.1", port=16965):
    self.address = address
    self.port = port
    self.protocol = None
    self.recieved = []
    self.outbound = []

  def setup(self):
    self.loop = asyncio.get_event_loop()
    do_create_server = self.loop.create_server(
      lambda: TCPClient(self),
      self.address,
      self.port
    )
    server = self.loop.run_until_complete(do_create_server)
    self.loop.run_forever()

  def respond_function_for(self, message):
    def rf(response):
      self.outbound.append(message)
    return rf

  def poll(self):
    result = [
      (sender, body, self.respond_function_for(body))
        for (sender, body) in self.received
    ]
    self.recieved = []
    return result

  def flush(self):
    while len(self.outbound) > 0:
      self.protocol.send_message(self.outbound.pop())

  def report_connection(self, protocol):
    self.protocol = protocol

  def report_message(self, sender, message):
    self.received.append((sender, message))

class TCPClient (asyncio.Protocol):
  def __init__(self, report_to):
    self.overseer = report_to
    self.transport = None

  def connection_made(self, transport):
    self.transport = transport
    self.overseer.report_connection(self)

  def connection_lost(self, exc):
    self.transport.close()
    self.transport = None

  def data_received(self, data):
    self.overseer.report_message("anon@tcp", data.decode())

  def send_message(self, msg):
    if self.transport:
      self.transport.write(msg.encode())
      return True
    return False
