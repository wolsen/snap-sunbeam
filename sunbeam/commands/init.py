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

import enum
import logging
from pathlib import Path

import click
from rich.console import Console
from snaphelpers import Snap

from sunbeam.commands import juju
from sunbeam.commands import microk8s
from sunbeam.jobs.common import ResultType

LOG = logging.getLogger(__name__)
console = Console()
snap = Snap()


class Role(enum.Enum):
    """The role that the current node will play

    This determines if the role will be a control plane node, a Compute node,
    or a Converged node. The role will help determine which particular services
    need to be configured and installed on the system.
    """
    CONTROL = 1
    COMPUTE = 2
    CONVERGED = 3

    def is_control_node(self) -> bool:
        """Returns True if the node requires control services.

        Control plane services are installed on nodes which are not designated
        for compute nodes only. This helps determine the role that the local
        node will play.

        :return: True if the node should have control-plane services,
                 False otherwise
        """
        return self.value != Role.COMPUTE

    def is_compute_node(self) -> bool:
        """Returns True if the node requires compute services.

        Compute services are installed on nodes which are not designated as
        control nodes only. This helps determine the services which are
        necessary to install.

        :return: True if the node should run Compute services,
                 False otherwise
        """
        return self.value != Role.CONTROL

    def is_converged_node(self) -> bool:
        """Returns True if the node requires control and compute services.

        Control and Compute services are installed on nodes which are
        designated as converged nodes. This helps determine the services
        which are necessary to install.

        :return: True if the node should run Control and Compute services,
                 False otherwise
        """
        return self.value == Role.CONVERGED


@click.command()
@click.option('--auto', default=False, is_flag=True,
              help='Automatically configure using the preselected defaults')
@click.option('--role', default='converged',
              type=click.Choice(['control', 'compute', 'converged'],
                                case_sensitive=False),
              help='Specify whether the node will be a control node, a '
                   'compute node, or a converged node (default)')
def init(auto: bool, role: str) -> None:
    """Initialises the local node.

    When initializing the local node you must choose the role the node will
    function as. The local node can be initialised as a control plane node,
    a Compute node, or a Converged node where both control plane and compute
    services run on the same machine. The default option is to run both control
    plane services and compute node services on the same node in a converged
    architecture.
    """
    # context = click.get_current_context(silent=True)

    node_role = Role[role.upper()]

    LOG.debug(f'Initialising: auto {auto}, role {role}')

    cloud = snap.config.get('control-plane.cloud')
    model = snap.config.get('control-plane.model')
    bundle: Path = snap.paths.common / 'etc' / 'bundles' / 'control-plane.yaml'

    plan = []

    if node_role.is_control_node():
        plan.append(juju.EnsureJujuInstalled())
        plan.append(microk8s.EnsureMicrok8sInstalled())
        plan.append(microk8s.EnableHighAvailability())
        plan.append(microk8s.EnableDNS())
        plan.append(microk8s.EnableStorage())
        plan.append(microk8s.EnableMetalLB())
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

    click.echo(f'Node has been initialised as a {role} node')


if __name__ == '__main__':
    init()
