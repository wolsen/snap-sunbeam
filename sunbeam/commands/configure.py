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
import json
import logging
import os
import shutil
import subprocess
from typing import Optional

import click
import pwgen
from rich.console import Console
from rich.prompt import Prompt
from snaphelpers import Snap

from sunbeam.commands import juju
from sunbeam.jobs.common import BaseStep, Result, ResultType, Status

LOG = logging.getLogger(__name__)
console = Console()
snap = Snap()


VARIABLE_DEFAULTS = {
    "user": {
        "username": "demo",
        "cidr": "192.168.122.0/24",
    },
    "external_network": {
        "cidr": "10.20.20.0/24",
        "start": "10.20.20.10",
        "end": "10.20.20.200",
        "physical_network": "physnet1",
        "network_type": "flat",
        "segmentation_id": 0,
    },
}


def _retrieve_admin_credentials(jhelper: juju.JujuHelper, model: str) -> dict:
    """Retrieve cloud admin credentials.

    Retrieve cloud admin credentials from keystone and
    return as a dict suitable for use with subprocess
    commands.  Variables are prefixed with OS_.
    """
    app = "keystone"
    action_cmd = "get-admin-account"
    action_result = asyncio.get_event_loop().run_until_complete(
        jhelper.run_action(model, app, action_cmd)
    )

    if action_result.get("return-code", 0) > 1:
        _message = "Unable to retrieve openrc from Keystone service"
        raise click.ClickException(_message)

    return {
        "OS_USERNAME": action_result.get("username"),
        "OS_PASSWORD": action_result.get("password"),
        "OS_AUTH_URL": action_result.get("public-endpoint"),
        "OS_USER_DOMAIN_NAME": action_result.get("user-domain-name"),
        "OS_PROJECT_DOMAIN_NAME": action_result.get("project-domain-name"),
        "OS_PROJECT_NAME": action_result.get("project-name"),
        "OS_AUTH_VERSION": action_result.get("api-version"),
        "OS_IDENTITY_API_VERSION": action_result.get("api-version"),
    }


class ConfigureCloudStep(BaseStep):
    """Default cloud configuration for all-in-one install."""

    def __init__(self, credentials: dict):
        super().__init__(
            "Configure OpenStack cloud", "Configuring OpenStack cloud for use"
        )
        self.admin_credentails = credentials
        self.terraform_tfvars = (
            snap.paths.user_common / "etc" / "configure" / "terraform.tfvars.json"
        )
        self.variables = VARIABLE_DEFAULTS
        if self.terraform_tfvars.exists():
            with open(self.terraform_tfvars, "r") as tfvars:
                self.variables.update(json.loads(tfvars.read()))

    def has_prompts(self) -> bool:
        return True

    def prompt(self, console: Optional["rich.console.Console"] = None) -> None:
        """Prompt the user for basic cloud configuration.

        Prompts the user for required information for cloud configuration.

        :param console: the console to prompt on
        :type console: rich.console.Console (Optional)
        """
        # User configuration
        self.variables["user"]["username"] = Prompt.ask(
            "Username to use for access to OpenStack",
            default=self.variables["user"]["username"],
            console=console,
        )
        self.variables["user"]["password"] = Prompt.ask(
            "Password to use for access to OpenStack",
            default=self.variables["user"].get("password", pwgen.pwgen(12)),
            console=console,
        )
        self.variables["user"]["cidr"] = Prompt.ask(
            "Network range to use for project network",
            default=self.variables["user"]["cidr"],
            console=console,
        )

        # External Network Configuration
        self.variables["external_network"]["cidr"] = Prompt.ask(
            "CIDR of network to use for external networking",
            default=self.variables["external_network"]["cidr"],
            console=console,
        )
        self.variables["external_network"]["start"] = Prompt.ask(
            "Start of IP allocation range for external network",
            default=self.variables["external_network"]["start"],
            console=console,
        )
        self.variables["external_network"]["end"] = Prompt.ask(
            "End of IP allocation range for external network",
            default=self.variables["external_network"]["end"],
            console=console,
        )
        self.variables["external_network"]["physical_network"] = Prompt.ask(
            "Neutron label for physical network to map to external network",
            default=self.variables["external_network"]["physical_network"],
            console=console,
        )
        self.variables["external_network"]["network_type"] = Prompt.ask(
            "Network type for access to external network",
            default=self.variables["external_network"]["network_type"],
            console=console,
            choices=["flat", "vlan"],
        )
        if self.variables["external_network"]["network_type"] == "vlan":
            self.variables["external_network"]["segmentation_id"] = Prompt.ask(
                "VLAN ID to use for external network",
                default=self.variables["external_network"]["segmentation_id"],
                console=console,
            )
        else:
            self.variables["external_network"]["segmentation_id"] = 0

        with open(self.terraform_tfvars, "w") as tfvars:
            tfvars.write(json.dumps(self.variables))

    def run(self, status: Optional[Status]) -> Result:
        """Execute configuration using terraform."""
        env = os.environ.copy()
        env.update(self.admin_credentails)
        try:
            # NOTE:
            # terraform init will install plugins from $SNAP/terraform-plugins
            # which is linked to from /usr/local/share/terraform/plugins
            terraform = str(snap.paths.snap / "bin" / "terraform")
            cmd = [terraform, "init"]
            LOG.debug(f'Running command {" ".join(cmd)}')
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                cwd=snap.paths.user_common / "etc" / "configure",
                env=env,
            )
            LOG.debug(
                f"Command finished. stdout={process.stdout}, stderr={process.stderr}"
            )
            cmd = [
                terraform,
                "apply",
                "-auto-approve",
            ]
            LOG.debug(f'Running command {" ".join(cmd)}')
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                cwd=snap.paths.user_common / "etc" / "configure",
                env=env,
            )
            LOG.debug(
                f"Command finished. stdout={process.stdout}, stderr={process.stderr}"
            )
            return Result(ResultType.COMPLETED)
        except subprocess.CalledProcessError as e:
            LOG.exception("Error configuring cloud")
            return Result(ResultType.FAILED, str(e))


@click.command()
def configure() -> None:
    """Configure cloud with some sane defaults."""
    # NOTE: install to user writable location
    src = snap.paths.snap / "etc" / "configure"
    dst = snap.paths.user_common / "etc" / "configure"
    LOG.debug(f"Updating {dst} from {src}...")
    shutil.copytree(src, dst, dirs_exist_ok=True)

    model = snap.config.get("control-plane.model")
    jhelper = juju.JujuHelper()
    admin_credentials = _retrieve_admin_credentials(jhelper, model)

    plan = [ConfigureCloudStep(credentials=admin_credentials)]
    for step in plan:
        LOG.debug(f"Starting step {step.name}")
        message = f"{step.description} ... "
        with console.status(message) as status:
            if step.has_prompts():
                status.stop()
                step.prompt(console)
                status.start()

            LOG.debug(f"Running step {step.name}")
            result = step.run(status)
            LOG.debug(
                f"Finished running step {step.name}. Result: {result.result_type}"
            )

        if result.result_type == ResultType.FAILED:
            console.print(f"{message}[red]failed[/red]")
            raise click.ClickException(result.message)

        console.print(f"{message}[green]done[/green]")

    asyncio.get_event_loop().run_until_complete(jhelper.disconnect_controller())

    # Read from TF vars
    username = "foobar"
    password = "foobar"
    domain_name = "users"

    console.print(f"""# openrc for {username}
export OS_AUTH_URL={admin_credentials['OS_AUTH_URL']}
export OS_USERNAME={username}
export OS_PASSWORD={password}
export OS_USER_DOMAIN_NAME={domain_name}
export OS_PROJECT_DOMAIN_NAME={domain_name}
export OS_PROJECT_NAME={username}
export OS_AUTH_VERSION"={admin_credentials['OS_AUTH_VERSION']}
export OS_IDENTITY_API_VERSION"={admin_credentials['OS_IDENTITY_API_VERSION']}
""")
