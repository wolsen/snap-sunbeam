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
import subprocess
from pathlib import Path
from typing import Optional

from semver import VersionInfo

from sunbeam.jobs.common import BaseStep, InstallSnapStep, Result, ResultType

LOG = logging.getLogger(__name__)


class EnsureJujuInstalled(InstallSnapStep):
    """Validates the Juju is installed.

    Note, this can go away if Juju adds an interface for us to know that it
    is present.
    """

    MIN_JUJU_VERSION = VersionInfo(2, 9, 30)

    def __init__(self, channel: str = "latest/stable"):
        super().__init__(snap="juju", channel=channel)


class BootstrapJujuStep(BaseStep):
    """Bootstraps the Juju controller."""

    def __init__(self, cloud):
        super().__init__("Bootstrap Juju", "Bootstrapping Juju into microk8s")

        self.controller_name = None
        self.cloud = cloud

    def _juju_cmd(self, *args):
        """Runs the specified juju command line command

        The command will be run using the json formatter. Invoking functions
        do not need to worry about the format or the juju command that should
        be used.

        For example, to run the juju bootstrap microk8s, this method should
        be invoked as:

          self._juju_cmd('bootstrap', 'microk8s')

        Any results from running with json are returned after being parsed.
        Subprocess execution errors are raised to the calling code.

        :param args: command to run
        :return:
        """
        cmd = ["/snap/bin/juju"]
        cmd.extend(args)
        cmd.extend(["--format", "json"])

        LOG.debug(f'Running command {" ".join(cmd)}')
        process = subprocess.run(cmd, capture_output=True, text=True, check=True)
        LOG.debug(
            f"Command finished. stdout={process.stdout}, " "stderr={process.stderr}"
        )

        return json.loads(process.stdout.strip())

    def is_skip(self, status: Optional["Status"] = None):
        """Determines if the step should be skipped or not.

        :return: True if the Step should be skipped, False otherwise
        """

        # Determine which kubernetes clouds are added
        try:
            clouds = self._juju_cmd("clouds")
            LOG.debug(f"Available clouds in juju are {clouds.keys()}")

            k8s_clouds = []
            for name, details in clouds.items():
                if details["type"] == "k8s":
                    k8s_clouds.append(name)

            LOG.debug(
                f"There are {len(k8s_clouds)} k8s clouds available: " f"{k8s_clouds}"
            )

            controllers = self._juju_cmd("controllers")

            LOG.debug(f"Found controllers: {controllers.keys()}")
            LOG.debug(controllers)
            controllers = controllers.get("controllers", {})
            if not controllers:
                return False

            existing_controllers = []
            for name, details in controllers.items():
                if details["cloud"] in k8s_clouds:
                    existing_controllers.append(name)

            LOG.debug(
                f"There are {len(existing_controllers)} existing k8s "
                f"controllers running: {existing_controllers}"
            )
            if not existing_controllers:
                return False

            # Simply use the first existing kubernetes controller we find.
            # We actually probably need to provide a way for this to be
            # influenced, but for now - we'll use the first controller.
            self.controller_name = existing_controllers[0]
            return True
        except subprocess.CalledProcessError as e:
            LOG.exception(
                "Error determining whether to skip the bootstrap "
                "process. Defaulting to not skip."
            )
            LOG.debug(e.stdout)
            return False

    def run(self, status: Optional["Status"] = None) -> Result:
        """Run the step to completion.

        Invoked when the step is run and returns a ResultType to indicate

        :return:
        """
        try:
            cmd = ["/snap/bin/juju", "clouds", "--format", "json"]
            LOG.debug(f'Running command {" ".join(cmd)}')
            process = subprocess.run(cmd, capture_output=True, text=True, check=True)
            LOG.debug(
                f"Command finished. stdout={process.stdout}, " "stderr={process.stderr}"
            )

            clouds = json.loads(process.stdout)
            if self.cloud not in clouds:
                LOG.critical("Could not find microk8s as a suitable cloud!")
                return Result(ResultType.FAILED, "Unable to bootstrap to microk8s")

            cmd = ["/snap/bin/juju", "bootstrap", self.cloud]
            LOG.debug(f'Running command {" ".join(cmd)}')
            process = subprocess.run(cmd, capture_output=True, text=True, check=True)
            LOG.debug(
                f"Command finished. stdout={process.stdout}, " "stderr={process.stderr}"
            )

            return Result(ResultType.COMPLETED)
        except subprocess.CalledProcessError as e:
            LOG.exception(f"Error bootstrapping juju: {e.stderr}")
            return Result(ResultType.FAILED, e.stdout)


class CreateModelStep(BaseStep):
    """Creates the specified model name."""

    def __init__(self, model: str):
        super().__init__("Create model", "Creating model")
        self.model = model

    def is_skip(self, status: Optional["Status"] = None):
        """Determines if the step should be skipped or not.

        :return: True if the Step should be skipped, False otherwise
        """
        cmd = ["/snap/bin/juju", "models", "--format", "json"]
        try:
            LOG.debug(f'Running command {" ".join(cmd)}')
            process = subprocess.run(cmd, capture_output=True, text=True, check=True)
            LOG.debug(
                f"Command finished. stdout={process.stdout}, " "stderr={process.stderr}"
            )

            models = json.loads(process.stdout.strip())

            LOG.debug(f"Found models: {models}")
            for model in models.get("models", []):
                if model["short-name"] == self.model:
                    return True

            # TODO(wolsen) how to tell which substrate the controller is
            #  capable of?
            return False
        except subprocess.CalledProcessError:
            LOG.exception("Error running juju models")
            return False

    def run(self, status: Optional["Status"] = None) -> Result:
        """Run the step to completion.

        Invoked when the step is run and returns a ResultType to indicate

        :return:
        """
        try:
            cmd = ["/snap/bin/juju", "add-model", self.model]
            LOG.debug(f'Running command {" ".join(cmd)}')
            process = subprocess.run(cmd, capture_output=True, text=True, check=True)
            LOG.debug(
                f"Command finished. stdout={process.stdout}, " "stderr={process.stderr}"
            )

            return Result(ResultType.COMPLETED)
        except subprocess.CalledProcessError as e:
            LOG.exception("Error bootstrapping juju")
            return Result(ResultType.FAILED, e.stdout)


class DeployBundleStep(BaseStep):
    """Creates the specified model name."""

    def __init__(self, model: str, bundle: Path):
        super().__init__("Deploy bundle", "Deploy bundle")

        self.model = model
        self.bundle = bundle
        self.options = ["--trust"]

    def is_skip(self, status: Optional["Status"] = None):
        """Determines if the step should be skipped or not.

        :return: True if the Step should be skipped, False otherwise
        """

        cmd = ["/snap/bin/juju", "status", "--model", self.model, "--format", "json"]

        try:
            LOG.debug(f'Running command {" ".join(cmd)}')
            process = subprocess.run(cmd, capture_output=True, text=True, check=True)
            LOG.debug(
                f"Command finished. stdout={process.stdout}, " "stderr={process.stderr}"
            )

            status = json.loads(process.stdout.strip())

            LOG.debug(f"Status of  models {self.model}: {status}")
            # TOCHK: Do we need to skip this step???

            return False
        except subprocess.CalledProcessError as e:
            LOG.exception("Error verifying juju status")
            LOG.warning(e.stdout)
            LOG.warning(e.stderr)
            return False

    def run(self, status: Optional["Status"] = None) -> Result:
        """Run the step to completion.

        Invoked when the step is run and returns a ResultType to indicate

        :return:
        """
        home = os.environ.get("SNAP_REAL_HOME")
        os.environ["JUJU_DATA"] = f"{home}/.local/share/juju"

        asyncio.get_event_loop().run_until_complete(self._run())
        return Result(ResultType.COMPLETED)

    async def _run(self) -> Result:
        """

        :return:
        """
        from juju.controller import Controller

        controller = Controller()
        await controller.connect()

        try:
            # Get the reference to the specified model
            model = await controller.get_model(self.model)
            applications = await model.deploy(
                f"local:{self.bundle}",
                trust=True,
            )

            await model.block_until(
                lambda: all(
                    unit.workload_status == "active"
                    for application in applications
                    for unit in application.units
                )
            )
        finally:
            await controller.disconnect()

        return Result(ResultType.COMPLETED)


class DestroyModelStep(BaseStep):
    """Destroys the specified model name."""

    def __init__(self, model: str):
        super().__init__("Destroy model", "Destroy model")

        self.model = model
        self.options = ["--destroy-storage", "-y"]

    def is_skip(self, status: Optional["Status"] = None):
        """Determines if the step should be skipped or not.

        :return: True if the Step should be skipped, False otherwise
        """
        cmd = ["/snap/bin/juju", "models", "--format", "json"]
        try:
            LOG.debug(f'Running command {" ".join(cmd)}')
            process = subprocess.run(cmd, capture_output=True, text=True, check=True)
            LOG.debug(
                f"Command finished. stdout={process.stdout}, " "stderr={process.stderr}"
            )

            models = json.loads(process.stdout.strip())

            LOG.debug(f"Found models: {models}")
            for model in models.get("models", []):
                if model["short-name"] == self.model:
                    return False

            return True
        except subprocess.CalledProcessError:
            LOG.exception("Error running juju models")
            return False

    def run(self, status: Optional["Status"] = None) -> Result:
        """Run the step to completion.

        Invoked when the step is run and returns a ResultType to indicate

        :return:
        """
        try:
            cmd = ["/snap/bin/juju", "destroy-model", self.model]
            if self.options:
                cmd.extend(self.options)
            LOG.debug(f'Running command {" ".join(cmd)}')
            process = subprocess.run(cmd, capture_output=True, text=True, check=True)
            LOG.debug(
                f"Command finished. stdout={process.stdout}, " "stderr={process.stderr}"
            )

            return Result(ResultType.COMPLETED)
        except subprocess.CalledProcessError as e:
            LOG.exception("Error destroying juju model")
            return Result(ResultType.FAILED, e.stdout)


class ModelStatusStep(BaseStep):
    """Get the status of the specified model name."""

    def __init__(
        self, model: str, states: Optional[Path] = None, timeout: Optional[int] = None
    ):
        super().__init__("Model status", "Status of the apps in the model")

        self.model = model
        self.states = states
        self.timeout = timeout

    def is_skip(self, status: Optional["Status"] = None):
        """Determines if the step should be skipped or not.

        :return: True if the Step should be skipped, False otherwise
        """
        cmd = ["/snap/bin/juju", "models", "--format", "json"]
        try:
            LOG.debug(f'Running command {" ".join(cmd)}')
            process = subprocess.run(cmd, capture_output=True, text=True, check=True)
            LOG.debug(
                f"Command finished. stdout={process.stdout}, " "stderr={process.stderr}"
            )

            models = json.loads(process.stdout.strip())

            LOG.debug(f"Found models: {models}")
            for model in models.get("models", []):
                if model["short-name"] == self.model:
                    return False

            return True
        except subprocess.CalledProcessError:
            LOG.exception("Error verifying juju status")
            return False

    def run(self, status: Optional["Status"] = None) -> Result:
        """Run the step to completion.

        Invoked when the step is run and returns a ResultType to indicate

        :return:
        """
        try:
            if self.states:

                """
                # Workaround for https://bugs.launchpad.net/juju/+bug/1990797
                import os
                snap_real_home = os.environ.get('SNAP_REAL_HOME')
                home = os.environ.get('HOME')
                src = Path(snap_real_home) / '.local' / 'share' / 'juju'
                dst = Path(home) / '.local' / 'share'
                os.makedirs(dst, exist_ok=True)
                dst = dst / 'juju'
                try:
                    os.symlink(src, dst)
                except FileExistsError:
                    pass
                LOG.debug('Symlink src {src} to dst {dst}')
                """
                home = os.environ.get("SNAP_REAL_HOME")
                os.environ["JUJU_DATA"] = f"{home}/.local/share/juju"

                # asyncio.run(
                #     zaza.model.async_wait_for_application_states(
                #         model_name=self.model, states=self.states,
                #         timeout=self.timeout
                #     )
                # )
        except Exception:  # noqa
            LOG.warning("Error occurred")
            LOG.exception("Exception raised")
        # except zaza.model.ModelTimeout:
        #     LOG.warn('Timedout waiting for apps to be active')
        # except zaza.model.UnitError as e:
        #     LOG.warn(e)

        try:
            cmd = [
                "/snap/bin/juju",
                "status",
                "--model",
                self.model,
                "--format",
                "json",
            ]

            LOG.debug(f'Running command {" ".join(cmd)}')
            process = subprocess.run(cmd, capture_output=True, text=True, check=True)
            LOG.debug(
                f"Command finished. stdout={process.stdout}, " "stderr={process.stderr}"
            )

            status = json.loads(process.stdout.strip())
            status_message = []
            for app, details in status.get("applications", {}).items():
                app_status = details.get("application-status", {}).get(
                    "current", "Unknown"
                )
                message = f"App {app} is in {app_status} state"
                status_message.append(message)

            return Result(ResultType.COMPLETED, status_message)
        except subprocess.CalledProcessError as e:
            LOG.exception("Error getting status of model")
            return Result(ResultType.FAILED, e.stdout)
