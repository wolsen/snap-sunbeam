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
from datetime import datetime
from typing import Optional

import click
import pwgen
from rich.console import Console
from rich.prompt import Confirm, Prompt
from snaphelpers import Snap

from sunbeam.commands.juju import JujuHelper
from sunbeam.commands.ohv import UpdateExternalNetworkConfigStep
from sunbeam.jobs.common import BaseStep, Result, ResultType, Status

LOG = logging.getLogger(__name__)
console = Console()
snap = Snap()


VARIABLE_DEFAULTS = {
    "user": {
        "username": "demo",
        "cidr": "192.168.122.0/24",
        "security_group_rules": True,
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


def _retrieve_admin_credentials(jhelper: JujuHelper, model: str) -> dict:
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


class UserOpenRCStep(BaseStep):
    """Generate openrc for created cloud user."""

    def __init__(self, auth_url: str, auth_version: str, openrc: str):
        super().__init__("Generate user openrc", "Generating openrc for cloud usage")
        self.auth_url = auth_url
        self.auth_version = auth_version
        self.openrc = openrc

    def is_skip(self, status: Optional["Status"] = None):
        """Determines if the step should be skipped or not.

        :return: True if the Step should be skipped, False otherwise
        """
        return False

    def run(self, status: Optional[Status]) -> Result:
        try:
            terraform = str(snap.paths.snap / "bin" / "terraform")
            cmd = [terraform, "output", "-json"]
            LOG.debug(f'Running command {" ".join(cmd)}')
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                cwd=snap.paths.user_common / "etc" / "configure",
            )
            LOG.debug(
                f"Command finished. stdout={process.stdout}, stderr={process.stderr}"
            )
            tf_output = json.loads(process.stdout)
            self._print_openrc(tf_output)
            return Result(ResultType.COMPLETED)
        except subprocess.CalledProcessError as e:
            LOG.exception("Error initializing Terraform")
            return Result(ResultType.FAILED, str(e))

    def _print_openrc(self, tf_output: dict) -> None:
        """Print openrc to console and save to disk using provided information"""
        _openrc = f"""# openrc for {tf_output["OS_USERNAME"]["value"]}
export OS_AUTH_URL={self.auth_url}
export OS_USERNAME={tf_output["OS_USERNAME"]["value"]}
export OS_PASSWORD={tf_output["OS_PASSWORD"]["value"]}
export OS_USER_DOMAIN_NAME={tf_output["OS_USER_DOMAIN_NAME"]["value"]}
export OS_PROJECT_DOMAIN_NAME={tf_output["OS_PROJECT_DOMAIN_NAME"]["value"]}
export OS_PROJECT_NAME={tf_output["OS_PROJECT_NAME"]["value"]}
export OS_AUTH_VERSION={self.auth_version}
export OS_IDENTITY_API_VERSION={self.auth_version}"""
        if self.openrc:
            message = f"Writing openrc to {self.openrc} ... "
            console.status(message)
            with open(self.openrc, "w") as f_openrc:
                os.fchmod(f_openrc.fileno(), mode=0o640)
                f_openrc.write(_openrc)
            console.print(f"{message}[green]done[/green]")
        else:
            console.print(_openrc)


class InitializeTerraformStep(BaseStep):
    """Initialize Terraform with providers for OpenStack."""

    def __init__(self):
        super().__init__(
            "Initialize Terraform", "Initializing Terraform from provider mirror"
        )

    def is_skip(self, status: Optional["Status"] = None):
        """Determines if the step should be skipped or not.

        :return: True if the Step should be skipped, False otherwise
        """
        return False

    def run(self, status: Optional[Status]) -> Result:
        """Initialise Terraform configuration from provider mirror,"""
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
            )
            LOG.debug(
                f"Command finished. stdout={process.stdout}, stderr={process.stderr}"
            )
            return Result(ResultType.COMPLETED)
        except subprocess.CalledProcessError as e:
            LOG.exception("Error initializing Terraform")
            return Result(ResultType.FAILED, str(e))


class ConfigureCloudStep(BaseStep):
    """Default cloud configuration for all-in-one install."""

    def __init__(self, credentials: dict):
        super().__init__(
            "Configure OpenStack cloud", "Configuring OpenStack cloud for use"
        )
        self.admin_credentials = credentials
        self.terraform_tfvars = (
            snap.paths.user_common / "etc" / "configure" / "terraform.tfvars.json"
        )
        self.variables = VARIABLE_DEFAULTS
        if self.terraform_tfvars.exists():
            with open(self.terraform_tfvars, "r") as tfvars:
                self.variables.update(json.loads(tfvars.read()))

    def is_skip(self, status: Optional["Status"] = None):
        """Determines if the step should be skipped or not.

        :return: True if the Step should be skipped, False otherwise
        """
        return False

    def has_prompts(self) -> bool:
        return True

    def prompt(self, console: Optional[Console] = None) -> None:
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
        self.variables["user"]["security_group_rules"] = Confirm.ask(
            "Setup security group rules for SSH and ICMP ingress",
            default=self.variables["user"].get("security_group_rules", True),
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
            os.fchmod(tfvars.fileno(), mode=0o640)
            tfvars.write(json.dumps(self.variables))

    def run(self, status: Optional[Status]) -> Result:
        """Execute configuration using terraform."""
        env = os.environ.copy()
        env.update(self.admin_credentials)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        tf_log = str(
            snap.paths.user_common / "etc" / "configure" / f"terraform-{timestamp}.log"
        )
        env.update({"TF_LOG": "INFO", "TF_LOG_PATH": tf_log})
        try:
            terraform = str(snap.paths.snap / "bin" / "terraform")
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
@click.option("-o", "--openrc", help="Output file for cloud access details.")
def configure(openrc: str = None) -> None:
    """Configure cloud with some sane defaults."""
    # NOTE: install to user writable location
    src = snap.paths.snap / "etc" / "configure"
    dst = snap.paths.user_common / "etc" / "configure"
    LOG.debug(f"Updating {dst} from {src}...")
    shutil.copytree(src, dst, dirs_exist_ok=True)

    model = snap.config.get("control-plane.model")
    jhelper = JujuHelper()
    admin_credentials = _retrieve_admin_credentials(jhelper, model)
    ext_network_file = (
        snap.paths.user_common / "etc" / "configure" / "terraform.tfvars.json"
    )

    plan = [
        InitializeTerraformStep(),
        ConfigureCloudStep(credentials=admin_credentials),
        UserOpenRCStep(
            auth_url=admin_credentials["OS_AUTH_URL"],
            auth_version=admin_credentials["OS_AUTH_VERSION"],
            openrc=openrc,
        ),
        UpdateExternalNetworkConfigStep(ext_network=ext_network_file),
    ]
    for step in plan:
        LOG.debug(f"Starting step {step.name}")
        message = f"{step.description} ... "
        with console.status(message) as status:
            if step.has_prompts():
                status.stop()
                step.prompt(console)
                status.start()

            if step.is_skip():
                LOG.debug(f"Skipping step {step.name}")
                console.print(f"{message}[green]done[/green]")
                continue

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
