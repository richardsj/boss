#!/usr/bin/env python

"""
A simple tokenised template parser written to be compatible with
Ant's copy & filter tasks (see, http://ant.apache.org/manual/Tasks/filter.html).
"""

__author__ = "Scott Wallace"
__version__ = "0.1"
__maintainer__ = "Scott Wallace"
__email__ = "scott@wallace.sh"
__status__ = "Production"

import os
import sys
import optparse
import shutil
import logging

def main():
    """Function to act as the main loop."""
    # Set log level
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Parse the CLI options
    logging.debug("Parsing commandline options")
    cliopts = optparse.OptionParser()
    cliopts.add_option(
        "-c",
        "--config",
        dest="configfile",
        help="Configuration properties file that contain TOKEN=VALUE"
    )
    cliopts.add_option(
        "-t",
        "--templates",
        dest="templates",
        help="Template tree that contain the tokenised files"
    )
    cliopts.add_option(
        "-d",
        "--destination",
        dest="destination",
        help="Destination directory to write the final configuration tree"
    )
    (options, _) = cliopts.parse_args()

    # Ensure the required CLI options are provided
    if None in [options.configfile, options.templates, options.destination]:
        cliopts.print_help()
        sys.exit(1)

    # Parse the configuration file into a dictionary
    values = {}
    try:
        logging.debug("Parsing configuration file: %s", options.configfile)
        config = open(options.configfile)
    except IOError, errormessage:
        logging.warning(errormessage)

    for line in config:
        try:
            (key, val) = line.split('=', 1)
            values[key] = val.strip()
            logging.debug(
                "Parsed key: \"%s\" and value: \"%s\"",
                key,
                values[key]
            )
        except ValueError:
            # Ignore "dodgy" lines
            logging.debug("Could not parse line: %s", line)

    # Traverse the tree
    for dirpath, dirnames, filenames in os.walk(options.templates):
        # Ignore SVN directories
        if ".svn" in dirnames:
            logging.debug("Ignoring .svn directory")
            dirnames.remove(".svn")

        # Iterate over the files
        for filename in filenames:
            logging.debug("Working on %s", filename)
            # Extract the relative path for use later
            relativepath = dirpath[(len(options.templates)+1):]

            infile = os.path.join(dirpath, filename)
            indata = open(infile)

            # Create the directory for the output file
            target_directory = os.path.join(options.destination, relativepath)
            try:
                os.stat(target_directory)
            except OSError:
                try:
                    os.makedirs(target_directory)
                except OSError:
                    # Ignore mkdir errors
                    logging.warning(
                        "Could not make directory: %s",
                        target_directory
                    )

            outfile = os.path.join(options.destination, relativepath, filename)
            logging.debug("Writing to %s", outfile)
            try:
                output = open(outfile, "w")
            except IOError, errormessage:
                logging.error(
                    "Could not open a file for writing: %s",
                    errormessage
                )
                sys.exit(2)

            # Iterate over the input file
            for line in indata:
                newline = line

                # Create a loop where tokens keep substituting until the line
                # doesn't change. Allows for nested tokens.
                replaced = 1
                while replaced == 1:
                    replaced = 0
                    # Find all the tokens in a line
                    for token in values.keys():
                        logging.debug(
                            "Replacing \"%s\" with \"%s\"", token, values[token]
                        )
                        newline = line.replace("@%s@" % token, values[token])

                        # Compare the lines, if different start the loop for the
                        # line again
                        if newline != line:
                            logging.debug("Line has changed.  Rechecking.")
                            line = newline
                            replaced = 1
                            break

                # Write the final substituted line to the output file
                output.write(newline)

            indata.close()
            output.close()

            logging.debug("Copying from %s to %s", infile, outfile)
            shutil.copymode(infile, outfile)
    return True

if __name__ == "__main__":
    main()
    sys.exit(0)
