#!/usr/bin/env python

# Base libraries
import os
import ConfigParser
import Boss

class server():
    """
    Class for the main BOSS server.
    """

    hosts = {}
    varmap = {}

    def __init__(self, project, environment, context):

        # Main config directory
        configdir = os.path.join(Boss.__install__, "conf")

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
        self.common_scriptdir = os.path.join(Boss.__install__, "common", "scripts")

        # Loop through each of the configured hosts
        for entry in hosts.split(","):
            # Try to work out the username and host for each entry
            item = entry.split("@")
            try:
                # Simply split on the '@' symbol
                hostname = item[1].strip()
                user = item[0].strip()

                # Determine if there is a deployment root set
                item = hostname.split(":")
                try:
                    # Now split on the ':' symbol
                    deploypath = item[1].strip()
                    hostname = item[0].strip()
                except IndexError:
                    deploypath = None
            except IndexError:
                # '@' symbol missing.  Assume just a hostname.
                hostname = item[0].strip()
                # Set the user to the default user, if available
                user = default_user

            self.hosts[hostname] = {}
            self.hosts[hostname]["user"] = user
            self.hosts[hostname]["path"] = deploypath

            # Perform the environment variable mappings, if any
            try:
                for var, value in bossconf.items("VAR MAPPING"):
                    self.varmap[var] = value
            except ConfigParser.NoSectionError:
                pass

