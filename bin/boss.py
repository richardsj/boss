#!/usr/bin/env python

# Base libraries
import sys
import os
import logging
import optparse
import ConfigParser

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

def deploy(project, environment, context):
    """Main deployment loop."""

    # Resolve the path of where BOSS is installed
    boss_basedir = os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), ".."))

    # Add the local lib/ directory to the Python path
    sys.path.append(os.path.join(boss_basedir, "lib"))
    sys.path.append(os.path.join(boss_basedir, "lib", "paramiko"))

    # Add the main boss class
    import Boss

    # Main config directory
    configdir = os.path.join(boss_basedir, "conf")

    # Read and parse the main BOSS config file
    configfile = os.path.join(configdir, "boss.conf")
    bossconf = ConfigParser.ConfigParser()
    bossconf.read(configfile)

    # Fetch the default user, if set
    try:
        default_user = bossconf.get("BOSS", "default user")
    except:
        default_user = os.getlogin()

    # Read and parse the main environment config file
    env_file = os.path.join(configdir, "{0}.conf".format(environment))
    envconf = ConfigParser.ConfigParser()
    envconf.read(env_file)

    # Get a list of the hosts to deploy to
    hosts = envconf.get(project, context)

    # Resolve the common-scripts directory
    common_scriptdir = os.path.join(boss_basedir, "common", "scripts")

    # Loop through each of the configured hosts
    for entry in hosts.split(","):
        # Try to work out the username and host for each entry
        item = entry.split("@")
        try:
            # Simply split on the '@' symbol
            host = item[1].strip()
            user = item[0].strip()

            # Determine if there is a deployment root set
            item = host.split(":")
            try:
                # Now split on the ':' symbol
                deploypath = item[1].strip()
                host = item[0].strip()
            except IndexError:
                deploypath = None
        except IndexError:
            # '@' symbol missing.  Assume just a hostname.
            host = item[0].strip()
            # Set the user to the default user, if available
            user = default_user

        # Transfer and run the scripts
        try:
            remotehost = Boss.client(host, user)
        except Exception, e:
            bosslog.error("""There was an error connecting to host "{0}": {1}""".format(host, e))
        else:
            # Pass through the basedir, environment, project and context to the client object
            remotehost.environment = environment
            remotehost.project = project
            remotehost.context = context

            # Perform the environment variable mappings, if any
            remotehost.varmap = {}
            try:
                for var, value in bossconf.items("VAR_MAPPING"):
                    remotehost.varmap[var] = value
            except ConfigParser.NoSectionError:
                pass

            # Send the main configuration templates, config values and pkg/ data
            try:
                remotehost.configure(deploypath)
            except Exception, e:
                raise Exception("There was a problem configuring the remote client, {0}: {1}".format(host, e))

            # Run the common scripts
            remotehost.deploy(common_scriptdir)

            # Run the project specific scripts
            remotehost.deploy()
        finally:
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
    try:
        deploy(options.project, options.environment, options.context)
    except Exception, e:
        bosslog.error("There was an error: {0}".format(e))
