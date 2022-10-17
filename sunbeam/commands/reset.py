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
from rich.console import Console
from snaphelpers import Snap

from sunbeam.commands import juju
from sunbeam.commands.init import Role
from sunbeam.jobs.common import ResultType

LOG = logging.getLogger(__name__)
console = Console()
snap = Snap()


@click.command()
def reset() -> None:
    """Resets the local node.

    Reset the node to the defaults.
    TODO:
    Single node:
    microk8s destroy-model openstack
    snap remove microk8s??
    snap remove juju??
    Multi node:
    microk8s remove-node
    """
    # context = click.get_current_context(silent=True)

    role = snap.config.get("node.role")
    node_role = Role[role.upper()]

    model = snap.config.get("control-plane.model")

    plan = []

    if node_role.is_compute_node() or node_role.is_converged_node():
        LOG.debug("Append steps to reset the compute node")

    if node_role.is_control_node() or node_role.is_converged_node():
        LOG.debug("Append steps to reset the control node")
        # FIXME: This needs to be done only in non HA
        # HA case, remove microk8s?? what if microk8s already
        # exists and getting used for other purposes
        plan.append(juju.DestroyModelStep(model))

    for step in plan:
        LOG.debug(f"Starting step {step.name}")
        message = f"{step.description} ... "
        with console.status(f"{step.description} ... "):
            if step.is_skip():
                LOG.debug(f"Skipping step {step.name}")
                console.print(f"{message}[green]Done[/green]")
                continue
            else:
                LOG.debug(f"Running step {step.name}")
                result = step.run()
                LOG.debug(
                    f"Finished running step {step.name}. "
                    f"Result: {result.result_type}"
                )

        if result.result_type == ResultType.FAILED:
            console.print(f"{message}[red]Failed[/red]")
            raise click.ClickException(result.message)

        console.print(f"{message}[green]Done[/green]")


if __name__ == "__main__":
    reset()
