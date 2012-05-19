#!/usr/bin/env python

# Base libraries
import sys
import os
import logging
import optparse

__install__ = os.path.realpath(os.path.join(sys.path[0], ".."))

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

    # Add the main boss class
    import Boss

    server = Boss.server(project, environment, context)

    for hostname in server.hosts:
        # Transfer and run the scripts
        try:
            remotehost = Boss.client(hostname, server.hosts[hostname]["user"])
        except Exception, e:
            bosslog.error("""There was an error connecting to host "{0}": {1}""".format(hostname, e))
        else:
            # Pass through the basedir, environment, project and context to the client object
            remotehost.environment = environment
            remotehost.project = project
            remotehost.context = context
            remotehost.varmap = server.varmap

            # Send the main configuration templates, config values and pkg/ data
            try:
                remotehost.configure(server.hosts[hostname]["path"])
            except Exception, e:
                raise Exception("There was a problem configuring the remote client, {0}: {1}".format(hostname, e))

            # Run the common scripts
            remotehost.deploy(server.common_scriptdir)

            # Run the project specific scripts
            remotehost.deploy()

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

    # Add the local lib/ directory to the Python path
    sys.path.append(os.path.join(__install__, "lib"))

    # GO!
    try:
        deploy(options.project, options.environment, options.context)
    except Exception, e:
        bosslog.error("There was an error: {0}".format(e))
