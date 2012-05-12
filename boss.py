#!/usr/bin/env python

import sys
import os
import subprocess
import logging
import cStringIO

class SingleLevelFilter(logging.Filter):
    """Class to filter out a single log level.  From, http://stackoverflow.com/questions/1383254/logging-streamhandler-and-standard-streams"""
    def __init__(self, passlevel, reject):
        self.passlevel = passlevel
        self.reject = reject

    def filter(self, record):
        if self.reject:
            return (record.levelno != self.passlevel)
        else:
            return (record.levelno == self.passlevel)

def runFiles(directory):
    """Function to execute scripts within a directory"""

    # Ensure the directory exists
    if not os.path.exists(directory):
        logger.warn("""Directory "{0}" does not exist.""".format(directory))
        return False

    # Walk the directory structure
    logger.info("{0}:".format(os.path.basename(directory)))
    for dirname, dirs, files in os.walk(directory):
        # Iterate over the files
        files.sort()
        for file in files:
            # Build a relative path to the script
            filepath = os.path.join(directory, file)
            # Ensure the script is executable
            if os.access(filepath, os.X_OK):
                logger.info("| {0}:".format(file))
                # Launch the script, via a shell, and redirect STDERR to STDOUT
                script = subprocess.Popen([r'"{0}"'.format(filepath)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
                output, errors = script.communicate()

                # Show the output of the script
                for line in cStringIO.StringIO(output):
                    logger.info("| | {0}".format(line.strip()))
                logger.info("")
            else:
                # Warn about a non-executable script
                logger.warn("""| {0}: not executable.  Skipping.""".format(file))
                logger.warn("")

    return True

def deploy():
    # Resolve the path of where BOSS is installed
    basedir = os.path.abspath(os.path.dirname(sys.argv[0]))

    # Resolve the common-scripts directory
    common_scriptdir = os.path.join(basedir, "common-scripts")

    # Run the files in the common-scripts directory
    runFiles(common_scriptdir)

if __name__ == "__main__":
    # Send INFO logging to stdout
    stdout = logging.StreamHandler(sys.stdout)
    infofilter = SingleLevelFilter(logging.INFO, False)
    stdout.addFilter(infofilter)

    # Send all other levels to stderr
    stderr = logging.StreamHandler(sys.stderr)
    otherfilter = SingleLevelFilter(logging.INFO, True)
    stderr.addFilter(otherfilter)

    # Add the filters to the root logger
    rootlogger = logging.getLogger()
    rootlogger.addHandler(stdout)
    rootlogger.addHandler(stderr)

    # Setup main logger
    logger = logging.getLogger("boss.logger")
    logger.setLevel(logging.DEBUG)
    deploy()
