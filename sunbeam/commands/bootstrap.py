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
from pathlib import Path

import click
from rich.console import Console
from snaphelpers import Snap

from sunbeam import utils
from sunbeam.commands import juju, ohv
from sunbeam.commands.init import Role
from sunbeam.jobs.common import ResultType

LOG = logging.getLogger(__name__)
console = Console()
snap = Snap()


@click.command()
def bootstrap() -> None:
    """Bootstrap the local node.

    Bootstrap juju.
    Deploy control plane if the node role is CONTROL.
    Depoy openstack-hypervisor snap if the node role
    is COMPUTE.
    """
    # context = click.get_current_context(silent=True)

    if utils.has_superuser_privileges():
        raise click.UsageError(
            "The bootstrap command should not be run with root "
            "privileges. Try again without sudo."
        )

    role = snap.config.get("node.role")
    node_role = Role[role.upper()]

    LOG.debug(f"Bootstrap node: role {role}")

    cloud = snap.config.get("control-plane.cloud")
    model = snap.config.get("control-plane.model")
    bundle: Path = snap.paths.common / "etc" / "bundles" / "control-plane.yaml"

    jhelper = juju.JujuHelper()

    plan = []

    if node_role.is_control_node():
        plan.append(juju.BootstrapJujuStep(cloud=cloud))
        plan.append(juju.CreateModelStep(jhelper=jhelper, model=model))
        plan.append(juju.DeployBundleStep(jhelper=jhelper, model=model, bundle=bundle))

    if node_role.is_compute_node():
        LOG.debug("This is where we would append steps for the compute node")
        plan.append(ohv.UpdateIdentityServiceConfigStep(jhelper=jhelper, model=model))
        plan.append(ohv.UpdateRabbitMQConfigStep(jhelper=jhelper, model=model))
        plan.append(ohv.UpdateNetworkConfigStep(jhelper=jhelper, model=model))

    for step in plan:
        LOG.debug(f"Starting step {step.name}")
        message = f"{step.description} ... "
        with console.status(f"{step.description} ... "):
            if step.is_skip():
                LOG.debug(f"Skipping step {step.name}")
                console.print(f"{message}[green]Done[/green]")
                continue

            LOG.debug(f"Running step {step.name}")
            result = step.run()
            LOG.debug(
                f"Finished running step {step.name}. " f"Result: {result.result_type}"
            )

        if result.result_type == ResultType.FAILED:
            console.print(f"{message}[red]Failed[/red]")
            raise click.ClickException(result.message)

        console.print(f"{message}[green]Done[/green]")

    click.echo(f"Node has been bootstrapped as a {role} node")
    asyncio.get_event_loop().run_until_complete(jhelper.disconnect_controller())


if __name__ == "__main__":
    bootstrap()
