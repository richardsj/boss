import os
import sys

__install__ = os.path.realpath(os.path.join(sys.path[0], ".."))
sys.path.append(os.path.join(__install__, "lib", "paramiko"))

from server import *
from client import *
