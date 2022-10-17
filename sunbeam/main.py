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

import logging

import click

from sunbeam.commands import bootstrap as bootstrap_cmds
from sunbeam.commands import init as init_cmds
from sunbeam.commands import reset as reset_cmds
from sunbeam.commands import status as status_cmds
from sunbeam import log


LOG = logging.getLogger()

# Update the help options to allow -h in addition to --help for
# triggering the help for various commands
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group('init', context_settings=CONTEXT_SETTINGS)
@click.option('--quiet', '-q', default=False, is_flag=True)
@click.option('--verbose', '-v', default=False, is_flag=True)
@click.pass_context
def cli(ctx, quiet, verbose):
    """Description of what the sunbeam command does.

    Yeah yeah yeah, I know this gets displayed on the commandline, but I don't
    yet know what to put here. I'll figure it out and then get back to it.
    """


def main():
    log.setup_root_logging()
    cli.add_command(init_cmds.init)
    cli.add_command(bootstrap_cmds.bootstrap)
    cli.add_command(reset_cmds.reset)
    cli.add_command(status_cmds.status)
    cli()


if __name__ == '__main__':
    main()
