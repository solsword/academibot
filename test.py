"""
test.py
academibot unit tests. These tests use direct input with spoofed contexts
instead of actually using email input/output. Tests are run sequentially.
"""

import academibot

# Tests are given as [input, output]:
tests = [
  ["""
   :help test
   """,
   """
   """]
]

if __name__ == "__main__":
