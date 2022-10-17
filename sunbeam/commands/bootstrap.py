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
from pathlib import Path

import click
from rich.console import Console
from snaphelpers import Snap

from sunbeam.commands.init import Role
from sunbeam.commands import juju
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

    role = snap.config.get('node.role')
    node_role = Role[role.upper()]

    LOG.debug(f'Bootstrap node: role {role}')

    cloud = snap.config.get('control-plane.cloud')
    model = snap.config.get('control-plane.model')
    bundle: Path = snap.paths.common / 'etc' / 'bundles' / 'control-plane.yaml'

    plan = []

    if node_role.is_control_node():
        plan.append(juju.BootstrapJujuStep(cloud=cloud))
        plan.append(juju.CreateModelStep(model))
        plan.append(juju.DeployBundleStep(model, bundle))

    if node_role.is_compute_node():
        LOG.debug('This is where we would append steps for the compute node')

    for step in plan:
        LOG.debug(f'Starting step {step.name}')
        message = f'{step.description} ... '
        with console.status(f'{step.description} ... '):
            if step.is_skip():
                LOG.debug(f'Skipping step {step.name}')
                console.print(f'{message}[green]Done[/green]')
                continue
            else:
                LOG.debug(f'Running step {step.name}')
                result = step.run()
                LOG.debug(f'Finished running step {step.name}. '
                          f'Result: {result.result_type}')

        if result.result_type == ResultType.FAILED:
            console.print(f'{message}[red]Failed[/red]')
            raise click.ClickException(result.message)

        console.print(f'{message}[green]Done[/green]')

    # if node_role.is_compute_node():
    #     with console.status('Configuring hypervisor...', spinner='dots'):
    #         LOG.debug('testing')
    #         time.sleep(5)
    #         LOG.debug('now sleeping for a little longer')
    #         time.sleep(5)
    #
    #     click.echo('Hypervisor has been configured')

    click.echo(f'Node has been bootstrapped as a {role} node')


if __name__ == '__main__':
    bootstrap()
