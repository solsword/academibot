"""
channel.py
Abstract "channel" class for implementing input feeds to academibot.
"""

class Channel:
  """
  An abstract class representing a communication method by which messages might
  arrive and be replied to.
  """
  def setup(self):
    """
    Perform any necessary setup tasks.
    """
    return

  def poll(self):
    """
    Returns a collection of sender, message, response_function tuples. To reply
    to a message, the caller will give a string to the response function.
    """
    return []

  def flush(self):
    """
    Called every cycle after message responses have been issued. Allows the
    channel to buffer responses if it wishes.
    """
    return
 
  def __str__(self):
    return "a channel"
