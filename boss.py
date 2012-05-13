#!/usr/bin/env python

import sys
import os
import subprocess
import logging
import cStringIO

# Try to import "paramiko" for SSH functionality
try:
    import paramiko
except Exception, e:
    logging.error("""BOSS requires "paramiko".  Please install paramiko before attempting to continue.  See, http://www.lag.net/paramiko/""")
    sys.exit(99)

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

class IgnoreMissingKeys(paramiko.MissingHostKeyPolicy):
    def missing_host_key(self, client, hostname, key):
        return

class BOSSclient():
    """Class for a remote BOSS client."""

    def __init__(self, hostname, username):
        # Set up an SSH client and set the key policy to ignore missing keys
        self.client = paramiko.SSHClient()
        self.client.load_system_host_keys()
        self.client.set_missing_host_key_policy(IgnoreMissingKeys)

        # Connect to the remote host
        try:
            self.client.connect(hostname, username=username)
        except Exception, e:
            raise Exception("There was a problem connecting to {0}@{1}: {2}".format(username, hostname, e))

        self.remotebasedir = "/var/tmp"

        # Output hostname
        bosslog.info(hostname)

    def execute(self, directory):
        """Copies a local directory to a remote host and executes the script."""

        # Build the remote path
        remotedir = os.path.join(self.remotebasedir, os.path.basename(directory))

        # Create an SFTP channel for transferring files
        sftp = self.client.open_sftp()
        sftp.mkdir(remotedir, 493)

        # Output the directory name
        bosslog.info("| {0}".format(os.path.basename(directory)))
        for dirname, dirs, files in os.walk(directory):
            files.sort()
            for file in files:
                # Build paths to the local and remote files
                local_file = os.path.join(directory, file)
                remote_file = os.path.join(remotedir, file)

                # Check for execute permissions
                if os.access(local_file, os.X_OK):
                    # Copy the local file to the remote host
                    sftp.put(local_file, remote_file)
                else:
                    # Warn about a non-executable script
                    bosslog.warn("""| {0}: not executable.  Skipping.""".format(file))
                    bosslog.warn("")
                    continue

                # Get the file permissions from the local file and apply them remotely
                lstat = os.stat(local_file)
                sftp.chmod(remote_file, lstat.st_mode)

                # Execute the remote script
                bosslog.info("| | {0}".format(os.path.basename(remote_file)))
                stdin, stdout, stderr = self.client.exec_command(remote_file)
                for line in stdout:
                    bosslog.info("| | | {0}".format(line.rstrip()))
                for line in stderr:
                    bosslog.warn("| | | {0}".format(line.rstrip()))

                sftp.remove(remote_file)
        sftp.rmdir(remotedir)

def deploy():
    # Resolve the path of where BOSS is installed
    basedir = os.path.abspath(os.path.dirname(sys.argv[0]))

    # Resolve the common-scripts directory
    common_scriptdir = os.path.join(basedir, "common-scripts")

    # Run the files in the common-scripts directory
    try:
        saturn = BOSSclient("saturn", "root")
    except Exception, e:
        bosslog.error(e)
    else:
        saturn.execute(common_scriptdir)

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

    # Setup main BOSS logger
    bosslog = logging.getLogger("boss.logger")
    bosslog.setLevel(logging.DEBUG)

    # GO!
    deploy()
