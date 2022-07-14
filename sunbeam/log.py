# Copyright (c) 2022 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import logging

from rich.logging import RichHandler


def setup_root_logging():
    """Sets up the root logging level for the application.

    By default, console logging will be turned off and file level logging
    will be turned to INFO level of trace.

    The logging is configured based upon execution context, such that
    if the user's command execution is requesting quieter or more verbose
    output the logging levels will adjust.

    This will also set up the file logging in order to get execution logs
    from machines, as well as configuring the console output logging levels.
    """
    logger = logging.getLogger()
    # By default, we'll enable all debug logging.
    logger.setLevel(logging.DEBUG)
    console = False

    # NOTE(wolsen) there must be a better way to do this. In theory, we can
    #  add this to the root command group and adopt the commands everywhere
    #  and analyze the context... but it was always parsed too late.
    for arg in sys.argv:
        if arg.lower() in ['-v', '--verbose']:
            console = True
            break

    # If the console is enabled, then enable the RichHandler as it will
    # put the log messages to the line and still honor current console
    # entries relevant to the user.
    if console:
        handler = RichHandler()
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter('%(message)s', datefmt='[%X]'))
        logger.addHandler(handler)

