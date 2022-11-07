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

import asyncio
import logging

import click
from rich.console import Console
from snaphelpers import Snap

from sunbeam.commands import juju

LOG = logging.getLogger(__name__)
console = Console()
snap = Snap()


@click.command()
def openrc() -> None:
    """openrc for admin account

    Retrieve openrc for cloud admin account
    """
    model = snap.config.get("control-plane.model")
    jhelper = juju.JujuHelper()

    with console.status("Retrieving openrc from Keystone service ... "):
        # Retrieve config from juju actions
        app = "keystone"
        action_cmd = "get-admin-account"
        action_result = asyncio.get_event_loop().run_until_complete(
            jhelper.run_action(model, app, action_cmd)
        )

        if action_result.get("return-code", 0) > 1:
            _message = "Unable to retrieve openrc from Keystone service"
            raise click.ClickException(_message)
        else:
            console.print(action_result.get("openrc"))

    asyncio.get_event_loop().run_until_complete(jhelper.disconnect_controller())
