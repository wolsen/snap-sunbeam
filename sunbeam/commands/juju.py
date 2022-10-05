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

import json
import logging
from pathlib import Path
import subprocess

from sunbeam.jobs.common import BaseStep
from sunbeam.jobs.common import Result
from sunbeam.jobs.common import ResultType
from sunbeam.snapd.client import Client


LOG = logging.getLogger(__name__)

MODEL_NAME = 'sunbeam'


class EnsureJujuInstalled(BaseStep):
    """Validates the Juju is installed.

    Note, this can go away if Juju adds an interface for us to know that it
    is present.
    """
    def __init__(self):
        super().__init__(name='Ensure Juju',
                         description='Checking for Juju installation')

    def run(self) -> Result:
        """Checks to see if Juju is installed..."""
        client = Client()
        snaps = client.snaps.get_installed_snaps(['juju'])
        if not snaps:
            LOG.debug('No snaps returned from query')
            return Result(ResultType.FAILED,
                          'Could not detect juju installation. Install '
                          'juju by running `sudo snap install juju` then '
                          'try again.')

        if len(snaps) > 1:
            LOG.debug('More than one snap named juju?')
            return Result(ResultType.FAILED, 'Too many juju clients installed')

        return Result(ResultType.COMPLETED)


class BootstrapJujuStep(BaseStep):
    """Bootstraps the Juju controller.

    """
    def __init__(self):
        super().__init__('Bootstrap Juju',
                         'Bootstrapping Juju into microk8s')

        self.controller_name = None

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
        cmd = ['/snap/bin/juju']
        cmd.extend(args)
        cmd.extend(['--format', 'json'])

        LOG.debug(f'Running command {" ".join(cmd)}')
        process = subprocess.run(cmd, capture_output=True, text=True,
                                 check=True)
        LOG.debug(f'Command finished. stdout={process.stdout}, '
                  'stderr={process.stderr}')

        return json.loads(process.stdout.strip())

    def is_skip(self):
        """Determines if the step should be skipped or not.

        :return: True if the Step should be skipped, False otherwise
        """

        # Determine which kubernetes clouds are added
        try:
            clouds = self._juju_cmd('clouds')
            LOG.debug(f'Available clouds in juju are {clouds.keys()}')

            k8s_clouds = []
            for name, details in clouds.items():
                if details['type'] == 'k8s':
                    k8s_clouds.append(name)

            LOG.debug(f'There are {len(k8s_clouds)} k8s clouds available: '
                      f'{k8s_clouds}')

            controllers = self._juju_cmd('controllers')

            LOG.debug(f'Found controllers: {controllers.keys()}')
            controllers = controllers.get('controllers', {})
            if not controllers:
                return False

            existing_controllers = []
            for name, details in controllers.items():
                if details['cloud'] in k8s_clouds:
                    existing_controllers.append(name)

            LOG.debug(f'There are {len(existing_controllers)} existing k8s '
                      f'controllers running: {existing_controllers}')
            if not existing_controllers:
                return False

            # Simply use the first existing kubernetes controller we find.
            # We actually probably need to provide a way for this to be
            # influenced, but for now - we'll use the first controller.
            self.controller_name = existing_controllers[0]
            return True
        except subprocess.CalledProcessError:
            LOG.exception('Error determining whether to skip the bootstrap '
                          'process. Defaulting to not skip.')
            return False

    def run(self) -> Result:
        """Run the step to completion.

        Invoked when the step is run and returns a ResultType to indicate

        :return:
        """
        try:
            cmd = ['/snap/bin/juju', 'clouds', '--format', 'json']
            LOG.debug(f'Running command {" ".join(cmd)}')
            process = subprocess.run(cmd, capture_output=True, text=True,
                                     check=True)
            LOG.debug(f'Command finished. stdout={process.stdout}, '
                      'stderr={process.stderr}')

            clouds = json.loads(process.stdout)
            if 'microk8s' not in clouds:
                LOG.critical('Could not find microk8s as a suitable cloud!')
                return Result(ResultType.FAILED,
                              'Unable to bootstrap to microk8s')

            cmd = ['/snap/bin/juju', 'bootstrap', 'microk8s']
            LOG.debug(f'Running command {" ".join(cmd)}')
            process = subprocess.run(cmd, capture_output=True, text=True,
                                     check=True)
            LOG.debug(f'Command finished. stdout={process.stdout}, '
                      'stderr={process.stderr}')

            return Result(ResultType.COMPLETED)
        except subprocess.CalledProcessError as e:
            LOG.exception(f'Error bootstrapping juju: {e.stderr}')
            return Result(ResultType.FAILED, e.stdout)


class CreateModelStep(BaseStep):
    """Creates the specified model name.

    """
    def __init__(self, model: str):
        super().__init__('Create model', 'Creating model')
        self.model = model

    def is_skip(self):
        """Determines if the step should be skipped or not.

        :return: True if the Step should be skipped, False otherwise
        """
        cmd = ['/snap/bin/juju', 'models', '--format', 'json']
        try:
            LOG.debug(f'Running command {" ".join(cmd)}')
            process = subprocess.run(cmd, capture_output=True, text=True,
                                     check=True)
            LOG.debug(f'Command finished. stdout={process.stdout}, '
                      'stderr={process.stderr}')

            models = json.loads(process.stdout.strip())

            LOG.debug(f'Found models: {models}')
            for model in models.get('models', []):
                if model['short-name'] == self.model:
                    return True

            # TODO(wolsen) how to tell which substrate the controller is
            #  capable of?
            return False
        except subprocess.CalledProcessError:
            LOG.exception('Error running juju models')
            return False

    def run(self) -> Result:
        """Run the step to completion.

        Invoked when the step is run and returns a ResultType to indicate

        :return:
        """
        try:
            cmd = ['/snap/bin/juju', 'add-model', self.model]
            LOG.debug(f'Running command {" ".join(cmd)}')
            process = subprocess.run(cmd, capture_output=True, text=True,
                                     check=True)
            LOG.debug(f'Command finished. stdout={process.stdout}, '
                      'stderr={process.stderr}')

            return Result(ResultType.COMPLETED)
        except subprocess.CalledProcessError as e:
            LOG.exception('Error bootstrapping juju')
            return Result(ResultType.FAILED, e.stdout)


class DeployBundleStep(BaseStep):
    """Creates the specified model name.

    """
    def __init__(self, model: str, bundle: Path):
        super().__init__('Deploy bundle', 'Deploy bundle')

        self.model = model
        self.bundle = bundle
        self.options = ["--trust"]

    def is_skip(self):
        """Determines if the step should be skipped or not.

        :return: True if the Step should be skipped, False otherwise
        """
        cmd = ['/snap/bin/juju', 'status', '--model', self.model,
               '--format', 'json']

        try:
            LOG.debug(f'Running command {" ".join(cmd)}')
            process = subprocess.run(cmd, capture_output=True, text=True,
                                     check=True)
            LOG.debug(f'Command finished. stdout={process.stdout}, '
                      'stderr={process.stderr}')

            status = json.loads(process.stdout.strip())

            LOG.debug(f'Status of  models {self.model}: {status}')
            # TOCHK: Do we need to skip this step???

            return False
        except subprocess.CalledProcessError:
            LOG.exception('Error verifying juju status')
            return False

    def run(self) -> Result:
        """Run the step to completion.

        Invoked when the step is run and returns a ResultType to indicate

        :return:
        """
        try:
            cmd = ['/snap/bin/juju', 'deploy', '--model', self.model,
                   str(self.bundle)]

            if self.options:
                cmd.extend(self.options)
            LOG.debug(f'Running command {" ".join(cmd)}')
            process = subprocess.run(cmd, capture_output=True, text=True,
                                     check=True)
            LOG.debug(f'Command finished. stdout={process.stdout}, '
                      'stderr={process.stderr}')

            return Result(ResultType.COMPLETED)
        except subprocess.CalledProcessError as e:
            LOG.exception('Error deploying juju bundle')
            return Result(ResultType.FAILED, e.stdout)


class DestroyModelStep(BaseStep):
    """Destroys the specified model name.

    """
    def __init__(self, model: str):
        super().__init__('Destroy model', 'Destroy model')

        self.model = model
        self.options = ['--destroy-storage', '-y']

    def is_skip(self):
        """Determines if the step should be skipped or not.

        :return: True if the Step should be skipped, False otherwise
        """
        cmd = ['/snap/bin/juju', 'models', '--format', 'json']
        try:
            LOG.debug(f'Running command {" ".join(cmd)}')
            process = subprocess.run(cmd, capture_output=True, text=True,
                                     check=True)
            LOG.debug(f'Command finished. stdout={process.stdout}, '
                      'stderr={process.stderr}')

            models = json.loads(process.stdout.strip())

            LOG.debug(f'Found models: {models}')
            for model in models.get('models', []):
                if model['short-name'] == self.model:
                    return False

            return True
        except subprocess.CalledProcessError:
            LOG.exception('Error running juju models')
            return False

    def run(self) -> Result:
        """Run the step to completion.

        Invoked when the step is run and returns a ResultType to indicate

        :return:
        """
        try:
            cmd = ['/snap/bin/juju', 'destroy-model', self.model]
            if self.options:
                cmd.extend(self.options)
            LOG.debug(f'Running command {" ".join(cmd)}')
            process = subprocess.run(cmd, capture_output=True, text=True,
                                     check=True)
            LOG.debug(f'Command finished. stdout={process.stdout}, '
                      'stderr={process.stderr}')

            return Result(ResultType.COMPLETED)
        except subprocess.CalledProcessError as e:
            LOG.exception('Error destroying juju model')
            return Result(ResultType.FAILED, e.stdout)


class ModelStatusStep(BaseStep):
    """Get the status of the specified model name.

    """
    def __init__(self, model: str):
        super().__init__('Model status', 'Status of the apps in the model')

        self.model = model

    def is_skip(self):
        """Determines if the step should be skipped or not.

        :return: True if the Step should be skipped, False otherwise
        """
        cmd = ['/snap/bin/juju', 'models', '--format', 'json']
        try:
            LOG.debug(f'Running command {" ".join(cmd)}')
            process = subprocess.run(cmd, capture_output=True, text=True,
                                     check=True)
            LOG.debug(f'Command finished. stdout={process.stdout}, '
                      'stderr={process.stderr}')

            models = json.loads(process.stdout.strip())

            LOG.debug(f'Found models: {models}')
            for model in models.get('models', []):
                if model['short-name'] == self.model:
                    return False

            return True
        except subprocess.CalledProcessError:
            LOG.exception('Error verifying juju status')
            return False

    def run(self) -> Result:
        """Run the step to completion.

        Invoked when the step is run and returns a ResultType to indicate

        :return:
        """
        try:
            cmd = ['/snap/bin/juju', 'status', '--model', self.model,
                   '--format', 'json']

            LOG.debug(f'Running command {" ".join(cmd)}')
            process = subprocess.run(cmd, capture_output=True, text=True,
                                     check=True)
            LOG.debug(f'Command finished. stdout={process.stdout}, '
                      'stderr={process.stderr}')

            status = json.loads(process.stdout.strip())
            status_message = []
            for app, details in status.get('applications', {}).items():
                app_status = details.get('application-status',
                                         {}).get('current', 'Unknown')
                message = f'App {app} is in {app_status} state'
                status_message.append(message)

            return Result(ResultType.COMPLETED, status_message)
        except subprocess.CalledProcessError as e:
            LOG.exception('Error getting status of model')
            return Result(ResultType.FAILED, e.stdout)
