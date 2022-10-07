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
import logging

from sunbeam.commands import juju
from sunbeam.jobs.common import ResultType

from rich.console import Console

LOG = logging.getLogger(__name__)
console = Console()


@click.command()
def status() -> None:
    """Status of the node.

    Print status of the cluster.
    """
    context = click.get_current_context(silent=True)

    model = 'sunbeam'

    plan = []

    plan.append(juju.ModelStatusStep(model))

    status_overall = []
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
                if result.result_type == ResultType.COMPLETED:
                    if isinstance(result.message, list):
                        status_overall.extend(result.message)
                    elif isinstance(result.message, str):
                        status_overall.append(result.message)
                LOG.debug(f'Finished running step {step.name}. '
                          f'Result: {result.result_type}')

        if result.result_type == ResultType.FAILED:
            console.print(f'{message}[red]Failed[/red]')
            raise click.ClickException(result.message)

    console.print('Sunbeam status:')
    for message in status_overall:
        if 'active' in message:
            console.print(f'[green]{message}[/green]')
        else:
            console.print(f'[red]{message}[/red]')

