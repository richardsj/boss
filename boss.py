#!/usr/bin/env python

import sys
import os
import logging
import optparse
import ConfigParser
import random
import string

# Try to import "paramiko" for SSH functionality
try:
    import paramiko
except Exception, e:
    logging.error("""BOSS requires "paramiko".  Please install paramiko before attempting to continue.  See, http://www.lag.net/paramiko/""")
    sys.exit(99)

boss_basedir = ""

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
    """Class to set up a policy to ignote missing SSH host keys."""
    def missing_host_key(self, client, hostname, key):
        return

class BOSSclient():
    """Class for a remote BOSS client."""

    config_dest = "/srv/cfg"
    tmpdir = "/var/tmp"

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

        # Generate a random string to avoid problems/conflicts
        rndstring = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(16))

        self.remote_basedir = os.path.join(self.tmpdir, "BOSS-{0}".format(rndstring))
        self.client.exec_command("mkdir -p {0}".format(self.remote_basedir))

        # Output hostname
        bosslog.info(hostname)

    def deploy(self):
        """Copies a local directory to a remote host and executes the scripts."""

        if not os.path.exists(self.project):
            bosslog.warn("""The "{0}" script directory does not exist.""".format(self.project))
            return False

        # Build the remote path
        remotedir = os.path.join(self.remote_basedir, os.path.basename(self.project))

        # Create an SFTP channel for transferring files
        sftp = self.client.open_sftp()
        sftp.mkdir(remotedir, 493)

        # Output the directory name
        bosslog.info("| {0}".format(os.path.basename(remotedir)))
        for dirname, dirs, files in os.walk(self.project):
            files.sort()
            for file in files:
                # Build paths to the local and remote files
                local_file = os.path.join(self.project, file)
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
        sftp.close()

    def configure(self, config_dest=None):

        if config_dest is None:
            config_dest = self.config_dest

        sftp = self.client.open_sftp()

        configroot = os.path.join(self.remote_basedir, ".configure")
        sftp.mkdir(configroot)

        for dirname, dirs, files in os.walk("templates"):
            sftp.mkdir(os.path.join(configroot, dirname))
            for file in files:
                sftp.put(os.path.join(dirname, file), os.path.join(configroot, dirname, file))

        for dirname, dirs, files in os.walk("conf"):
            sftp.mkdir(os.path.join(configroot, dirname))
            for file in files:
                sftp.put(os.path.join(dirname, file), os.path.join(configroot, dirname, file))

        sftp.put(os.path.join(boss_basedir, "lib", "detoken.py"), os.path.join(configroot, "detoken.py"))
        sftp.chmod(os.path.join(configroot, "detoken.py"), 0755)

        sftp.mkdir(config_dest)
        bosslog.debug("{0} -c {1} -t {2} -d {3}".format(os.path.join(configroot, "detoken.py"),
                                    os.path.join(configroot, "conf", "{0}-{1}.properties".format(self.context, self.environment)),
                                    os.path.join(configroot, "templates"),
                                    config_dest
                                ))
        stdin, stdout, stderr = self.client.exec_command("{0} -c {1} -t {2} -d {3}".format(os.path.join(configroot, "detoken.py"),
                                    os.path.join(configroot, "conf", "{0}-{1}.properties".format(self.context, self.environment)),
                                    os.path.join(configroot, "templates"),
                                    config_dest
                                ))
        for line in stdout:
            bosslog.info(line.rstrip())
        for line in stderr:
            bosslog.warn(line.rstrip())

        sftp.rmdir(configroot)
        sftp.close()

    def __del__(self):
        sftp = self.client.open_sftp()
        sftp.rmdir(self.remote_basedir)
        sftp.close()

        self.client.close()

def deploy(project, environment, context):
    """Main deployment loop."""

    # Resolve the path of where BOSS is installed
    boss_basedir = os.path.abspath(os.path.dirname(sys.argv[0]))

    configdir = os.path.join(boss_basedir, "conf")

    # Read and parse the main BOSS config file
    configfile = os.path.join(configdir, "boss.conf")
    bossconf = ConfigParser.ConfigParser()
    bossconf.read(configfile)

    # Fetch the default user, if set
    default_user = bossconf.get("BOSS", "default user")

    # Read and parse the main environment config file
    hostlistfile = os.path.join(configdir, "{0}-servers.conf".format(environment))
    hostlist = ConfigParser.ConfigParser()
    hostlist.read(hostlistfile)

    # Get a list of the hosts to deploy to
    hosts = hostlist.get(project, context)

    # Resolve the common-scripts directory
    common_scriptdir = os.path.join(boss_basedir, "common-scripts")

    # Loop through each of the configured hosts
    for entry in hosts.split(","):
        # Try to work out the username and host for each entry
        item = entry.split("@")
        try:
            # Simply split on the '@' symbol
            host = item[1].strip()
            user = item[0].strip()
        except IndexError:
            # '@' symbol missing.  Assume just a hostname.
            host = item[0].strip()
            # Set the user to the default user, if available
            if default_user:
                user = default_user
            else:
                # Otherwise use the current user.
                user = os.getlogin()

        # Transfer and run the files in the common-scripts directory
        try:
            remotehost = BOSSclient(host, user)
        except Exception, e:
            bosslog.error(e)
        else:
            # Pass through the environment, project and context to the client object
            remotehost.environment = environment
            remotehost.project = project
            remotehost.context = context

            remotehost.configure()
            #remotehost.deploy(common_scriptdir)
            #remotehost.deploy()

            del remotehost

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

    # Get the command line options
    parser = optparse.OptionParser()
    parser.add_option("-p", "--project", dest="project", help="The project scripts to execute.")
    parser.add_option("-e", "--env", dest="environment", help="The environment to delploy to.")
    parser.add_option("-c", "--context", dest="context", help="The context of the project.")
    (options, args) = parser.parse_args()

    # Ensure all three 'options' are provided
    if (not options.project or not options.environment or not options.context):
        bosslog.error(parser.print_help())
        sys.exit(1)

    # GO!
    deploy(options.project, options.environment, options.context)
