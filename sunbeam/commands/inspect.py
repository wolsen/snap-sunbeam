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
import datetime
import logging
import tarfile
import tempfile
from pathlib import Path

import click
from rich.console import Console
from snaphelpers import Snap

from sunbeam.commands import juju
from sunbeam.jobs.common import ResultType

LOG = logging.getLogger(__name__)
console = Console()
snap = Snap()


@click.command()
def inspect() -> None:
    """Inspect the microstack installation.

    This script will inspect your microstack installation. It will report any
    issue it finds, and create a tarball of logs and traces which can be
    attached to an issue filed against the microstack project.
    """
    model = snap.config.get("control-plane.model")
    time_stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"microstack-inspection-report-{time_stamp}.tar.gz"
    dump_file: Path = Path(snap.paths.user_common) / file_name
    jhelper = juju.JujuHelper()
    plan = []
    with tempfile.TemporaryDirectory() as tmpdirname:
        plan.append(
            juju.WriteModelStatusStep(
                jhelper=jhelper, model=model, file_path=tmpdirname + "/juju_status.out"
            )
        )
        plan.append(
            juju.WriteCharmLog(
                jhelper=jhelper, model=model, file_path=tmpdirname + "/debug_log.out"
            )
        )

        for step in plan:
            LOG.debug(f"Starting step {step.name}")
            with console.status(f"{step.description} ... "):
                if step.is_skip():
                    LOG.debug(f"Skipping step {step.name}")
                    continue

                result = step.run()
                if result.result_type == ResultType.COMPLETED:
                    console.print(f"[green]{result.message}[/green]")
                elif result.result_type == ResultType.FAILED:
                    console.print(f"{result.message}[red]failed[/red]")
                    console.print()
                    raise click.ClickException(result.message)
                LOG.debug(
                    f"Finished running step {step.name}. "
                    f"Result: {result.result_type}"
                )

        with tarfile.open(dump_file, "w:gz") as tar:
            tar.add(tmpdirname, arcname="./")

        console.print(f"[green]Output file written to {dump_file}[/green]")

    asyncio.get_event_loop().run_until_complete(jhelper.disconnect_controller())
