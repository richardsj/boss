import os
import sys
import logging

# Work out our installation directory
__install__ = os.path.realpath(os.path.join(sys.path[0], ".."))

# Find our logger
bosslog = logging.getLogger("boss.logger")

# Try to add a path to Paramiko
sys.path.append(os.path.join(__install__, "lib", "paramiko"))

from server import *
from client import *
