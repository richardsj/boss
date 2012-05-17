import os
import sys
import random
import string
import logging

# Use the main BOSS logger
bosslog = logging.getLogger("boss.logger")

# Try to import "paramiko" for SSH functionality
try:
    import paramiko
except Exception, e:
    bosslog.error("""BOSS requires "paramiko".  Please install paramiko before attempting to continue.  See, http://www.lag.net/paramiko/""")
    sys.exit(99)

class IgnoreMissingKeys(paramiko.MissingHostKeyPolicy):
    """Class to set up a policy to ignote missing SSH host keys."""

    def missing_host_key(self, client, hostname, key):
        """Class method to handle missing host keys."""

        # Do nothing.
        return

class client():
    """Class for a remote BOSS client."""

    tmpdir = "/tmp"
    deployroot = "/"

    def __init__(self, hostname, username):
        # Detect the main BOSS base directory
        self.boss_basedir = os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), ".."))

        # Set up an SSH client and set the key policy to ignore missing keys
        self.client = paramiko.SSHClient()
        self.client.load_system_host_keys()
        missingKeyPolicy = IgnoreMissingKeys()
        self.client.set_missing_host_key_policy(missingKeyPolicy)

        # Connect to the remote host
        try:
            self.client.connect(hostname, username=username)
        except Exception, e:
            raise Exception("There was a problem connecting to {0}@{1}: {2}".format(username, hostname, e))

        # Generate a random string to avoid problems/conflicts
        rndstring = "".join(random.choice(string.ascii_uppercase + string.digits) for x in range(16))

        self.remote_basedir = os.path.join(self.tmpdir, "BOSS-{0}".format(rndstring))
        self.mkdirs(self.remote_basedir)

        # Output hostname
        bosslog.info(hostname)

    def buildVarlist(self):
        """Class method to put a simple string that sets all the environment varibles needed for the remote scripts."""
        varlist = {}

        # Set the main BOSS variables
        varlist["ENVIRONMENT"] = self.environment
        varlist["PROJECT"] = self.project
        varlist["CONTEXT"] = self.context

        # Set any additional variable mappings
        for name, value in self.varmap.iteritems():
            try:
                varlist[name.upper()] = varlist[value.upper()]
            except Exception, e:
                varlist[name.upper()] = ""

        # Build a single string
        envlist = ""
        for name, value in varlist.iteritems():
            envlist = "{0} {1}={2}".format(envlist, name, value)

        return envlist

    def mkdirs(self, directory):
        """Class method to recursively make directories on a remote client."""

        (stdin, stdout, stderr) = self.client.exec_command("mkdir -p {0}".format(directory))
        # Read the stderr to ensure we let the mkdir command complete.  [ISSUE-5]
        stderr.read()

    def rmdirs(self, directory):
        """Class method to recursively delete directories on a remote client."""

        self.client.exec_command("rm -rf {0}".format(directory))

    def pushDirectory(self, src_dir, dst_dir):
        """Class method to copy the contents of a directory to a remote host."""

        self.mkdirs(dst_dir)

        sftp = self.client.open_sftp()

        # Count how many directories deep so we can avoid sending too deep
        pathskip = len(src_dir.split(os.sep))

        # Recurse the local directory and copy its content to the remote host
        for dirname, dirs, files in os.walk(src_dir):
            shortdir = os.sep.join(dirname.split(os.sep)[pathskip:])
            self.mkdirs(os.path.join(dst_dir, shortdir))
            for file in files:
                local_file = os.path.join(dirname, file)
                remote_file = os.path.join(dst_dir, shortdir, file)

                # Copy and duplicate permissions
                try:
                    sftp.put(local_file, remote_file)
                except Exception, e:
                    raise Exception("File copy failed: {0}".format(e))

                sftp.chmod(remote_file, os.stat(local_file).st_mode)

        sftp.close()

    def deploy(self, scriptdir=None):
        """Class method to copy a local directory to a remote host and executes the scripts within."""

        # Default to the supplied project for the script directory
        if not scriptdir:
            scriptdir = os.path.join(self.boss_basedir, "projects", self.project, "scripts")

        # Warn if there's no scripts to run
        if not os.path.exists(scriptdir):
            bosslog.warn("""The "{0}" script directory does not exist.""".format(scriptdir))
            return False

        # Build the remote path and sure it exists on the remote host
        remotedir = os.path.join(self.remote_basedir, os.path.basename(scriptdir))
        self.mkdirs(remotedir)

        # Build a list of the environment variables to pass through
        envlist = self.buildVarlist()

        # Create an SFTP channel for transferring files
        sftp = self.client.open_sftp()

        # Output the directory name
        bosslog.info("| {0}".format(os.path.basename(remotedir)))
        for dirname, dirs, files in os.walk(scriptdir):
            files.sort()
            for file in files:
                # Build paths to the local and remote files
                local_file = os.path.join(scriptdir, file)
                remote_file = os.path.join(remotedir, file)

                # Check for execute permissions
                if os.access(local_file, os.X_OK):
                    # Copy the local file to the remote host
                    sftp.put(local_file, remote_file)
                else:
                    # Warn about a non-executable script
                    bosslog.warn("""| {0}: not executable.  Skipping.""".format(file))
                    continue

                # Get the file permissions from the local file and apply them remotely
                lstat = os.stat(local_file)
                sftp.chmod(remote_file, lstat.st_mode)

                # Execute the remote script
                bosslog.info("| | {0}".format(os.path.basename(remote_file)))
                stdin, stdout, stderr = self.client.exec_command("{0} {1}".format(envlist, remote_file))
                for line in stdout:
                    bosslog.info("| | | {0}".format(line.rstrip()))
                for line in stderr:
                    bosslog.warn("| | | {0}".format(line.rstrip()))

        self.rmdirs(remotedir)
        sftp.close()

    def configure(self, root=None):
        """Class method to copy over the configuration templates and values and peform detokenisation."""

        # Use the default config destination if none is provided
        if root is None:
            root = self.deployroot

        # Create a directory to perform the configuration detokenisation
        configroot = os.path.join(self.remote_basedir, ".configure")

        self.pushDirectory(os.path.join(self.boss_basedir, "projects", self.project, "templates"), os.path.join(configroot, "templates"))
        self.pushDirectory(os.path.join(self.boss_basedir, "projects", self.project, "conf"), os.path.join(configroot, "conf"))
        self.pushDirectory(os.path.join(self.boss_basedir, "projects", self.project, "pkg"), os.path.join(root))

        # Copy over the lib/detoken.py script and set the permissions
        sftp = self.client.open_sftp()
        sftp.put(os.path.join(self.boss_basedir, "bin", "detoken.py"), os.path.join(configroot, "detoken.py"))
        sftp.chmod(os.path.join(configroot, "detoken.py"), 0755)
        sftp.close()

        # Run the detokeniser
        bosslog.info("| Detokenising the configuration templates")
        self.mkdirs(root)
        channel = self.client.get_transport().open_session()

        # Combine the output for stdout and stderr
        channel.set_combine_stderr(True)

        channel.exec_command("{0} -c {1} -t {2} -d {3}".format(os.path.join(configroot, "detoken.py"),
                             os.path.join(configroot, "conf", "{0}-{1}.properties".format(self.context, self.environment)),
                             os.path.join(configroot, "templates"),
                             root
                            ))

        # Wait for the command to finish and get the returncode
        errorcode = channel.recv_exit_status()

        output = []
        # Display stderr
        while channel.recv_stderr_ready():
            output.append(channel.recv_stderr(8192))
        output = "".join(output).split("\n")
        for line in output:
            bosslog.error("| | {0}".format(line.rstrip()))

        channel.close()

        if errorcode > 0:
            raise Exception("The detokenisation process failed.")

    def __del__(self):
        # Attempt to tidy-up the temporary directory on the remote host
        try:
            self.rmdirs(self.remote_basedir)
            self.client.close()
        except AttributeError:
            pass
