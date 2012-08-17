#!/usr/bin/env python

from utils import *

def setup():
  import subprocess

  line_break()
  print("Installing PIP...")
  subprocess.call(['sudo', 'easy_install-2.7', 'pip'])

  line_break()
  print("Installing Fabric...")
  subprocess.call(['pip', 'install', 'fabric'])

  line_break()
  print("Installing YAML...")
  subprocess.call(['pip', 'install', 'PyYAML'])

  line_break()
  print("DONE!  You're good to go!")

if __name__ == "__main__":
  setup()