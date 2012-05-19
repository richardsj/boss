#!/usr/bin/env python

# Base libraries
import os
import ConfigParser
import Boss

class server():
    """
    Class for the main BOSS system.
    """

    hosts = {}
    varmap = {}

    def __init__(self, project, environment, context):
        self.project = project
        self.environment = environment
        self.context = context

        # Main config directory
        configdir = os.path.join(Boss.__install__, "conf")

        # Read and parse the main BOSS config file
        conf_file = os.path.join(configdir, "boss.conf")
        self.bossconf = ConfigParser.ConfigParser()
        self.bossconf.read(conf_file)

        # Read and parse the per-project config file
        proj_file = os.path.join(Boss.__install__, "projects", self.project, "project.conf")
        self.projconf = ConfigParser.ConfigParser()
        self.projconf.read(proj_file)

        # Resolve the common-scripts directory
        self.common_scriptdir = os.path.join(Boss.__install__, "common", "scripts")

        # Loop through each of the configured hosts
        hosts = self.resolve_option(self.context)

        if not hosts:
            raise Exception("There was a problem finding hosts for context ({0})".format(self.context))

        for hostname in hosts.split(","):
            self.hosts[hostname] = {}
            self.hosts[hostname]["user"] = self.resolve_option("ssh user", default=os.getlogin())
            self.hosts[hostname]["path"] = self.resolve_option("deploy path")

            # Perform the environment variable mappings, if any
            try:
                for var, value in self.bossconf.items("VAR MAPPING"):
                    self.varmap[var] = value
            except ConfigParser.NoSectionError:
                pass

    def resolve_option(self, option, default=None):
        """
        Method to resolve a configuration option by checking the per-project configuration first
        followed by the main BOSS configuration before falling back to the provided default.
        """

        # Check the per-environment project config
        try:
            return self.projconf.get(self.environment, option)
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError), e:
            # Check project-wide config
            try:
                return self.projconf.get("PROJECT", option)
            except (ConfigParser.NoOptionError, ConfigParser.NoSectionError), e:
                # Check the main BOSS config
                try:
                    return self.bossconf.get("BOSS", option)
                except (ConfigParser.NoOptionError, ConfigParser.NoSectionError), e:
                    # Fallback to the default
                    return default

    def deploy(self):
        for hostname in self.hosts:
            # Transfer and run the scripts
            try:
                remotehost = Boss.client(hostname, server.hosts[hostname]["user"])
            except Exception, e:
                raise Exception("""There was an error connecting to host "{0}": {1}""".format(hostname, e))
            else:
                # Pass through the basedir, environment, project and context to the client object
                remotehost.environment = self.environment
                remotehost.project = self.project
                remotehost.context = self.context
                remotehost.varmap = self.varmap

                # Send the main configuration templates, config values and pkg/ data
                try:
                    remotehost.configure(self.hosts[hostname]["path"])
                except Exception, e:
                    raise Exception("There was a problem configuring the remote client, {0}: {1}".format(hostname, e))

                # Run the common scripts
                remotehost.deploy(self.common_scriptdir)

                # Run the project specific scripts
                remotehost.deploy()

                del remotehost
