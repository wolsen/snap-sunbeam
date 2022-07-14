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

import click

import requests
import requests_unixsocket

from pathlib import Path
from sunbeam.snapd.snaps import SnapService
from sunbeam.snapd.changes import ChangeService
from sunbeam.snapd.changes import Status


class Client:
    """A client for interacting with the Snapd API.

    """
    def __init__(self, version: str = 'v2',
                 socket_path: Path = '/run/snapd.socket'):
        super(Client, self).__init__()
        self.__version = version
        self.__socket_path = socket_path
        self._session = requests.sessions.Session()
        self._session.mount(requests_unixsocket.DEFAULT_SCHEME,
                            requests_unixsocket.UnixAdapter())
        self.snaps = SnapService(self._session)
        self.changes = ChangeService(self._session)


@click.group()
def main() -> None:
    """This is a simple python snap-client."""
    pass


@main.command()
@click.argument('snap')
@click.option('--channel', default='latest/stable')
@click.option('--classic', is_flag=True, help='Install in classic mode')
def install(snap, channel, classic):
    """Installs the specified snap"""
    client = Client()
    change_id = client.snaps.install(snap, channel, classic=classic)

    client.changes.wait_until(change_id, [Status.DoneStatus,
                                          Status.ErrorStatus])


@main.command()
@click.argument('snap')
def show(snap):
    """Shows details about the specified snap."""
    client = Client()
    snaps = client.snaps.get_installed_snaps(snap)
    if snaps:
        print(snaps[0].json())
    else:
        print("'{}'")


#
# Allow this to run as a main application for the purposes of interacting with
# the snapd socket as the root user. This is due to running into conflicts
# between juju and snapd with which level of privilege is desired.
#
# Conversely, the snapd cli is kind of difficult to work with from a scripting
# perspective.
#
if __name__ == '__main__':
    main.add_command(install)
    main()
