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
import subprocess

from sunbeam.jobs.common import BaseStep
from sunbeam.jobs.common import Result
from sunbeam.jobs.common import ResultType
from sunbeam.snapd.changes import Status
from sunbeam.snapd.client import Client


LOG = logging.getLogger(__name__)


class EnsureMicrok8sInstalled(BaseStep):
    """Validates microk8s is installed.

    Note, this can go away if we can default include the microk8s snap
    """
    def __init__(self, channel: str = 'latest/stable'):
        super().__init__(name='Ensure microk8s',
                         description='Checking for microk8s installation')
        self.channel = channel

    def run(self) -> Result:
        """Checks to see if microk8s is installed..."""
        client = Client()
        snaps = client.snaps.get_installed_snaps(['microk8s'])
        if not snaps:
            LOG.debug('No snaps returned from query')

            change_id = client.snaps.install('microk8s',
                                             self.channel,
                                             classic=False)
            client.changes.wait_until(change_id, [Status.DoneStatus,
                                                  Status.ErrorStatus])

        if len(snaps) > 1:
            LOG.debug('More than one snap named microk8s?')
            return Result(ResultType.FAILED,
                          'Too many microk8s snaps installed.')

        return Result(ResultType.COMPLETED)


class BaseCoreMicroK8sEnableStep(BaseStep):
    """Base add-on enablement step"""

    def __init__(self, addon: str, *args):
        """Enables high availability for the microk8s cluster"""
        super().__init__(f'Enable microk8s {addon}',
                         f'Enabling microk8s {addon} add-on')
        self._addon = addon
        self._args = None
        if len(args):
            self._args = [a for a in args]

    def is_skip(self):
        """Determines if the step should be skipped or not.

        :return: True if the Step should be skipped, False otherwise
        """
        cmd = ['/snap/bin/microk8s', 'status', '-a', self._addon]
        try:
            LOG.debug(f'Running command {" ".join(cmd)}')
            process = subprocess.run(cmd, capture_output=True, text=True,
                                     check=True)
            LOG.debug(f'Command finished. stdout={process.stdout}, '
                      'stderr={process.stderr}')
            return process.stdout.strip() == 'enabled'
        except subprocess.CalledProcessError:
            LOG.exception('Error determining ha-cluster add on status')
            return False

    def run(self) -> Result:
        """Run the step to completion.

        Invoked when the step is run and returns a ResultType to indicate

        :return:
        """
        cmd = ['/snap/bin/microk8s', 'enable', self._addon]
        if self._args:
            cmd.extend(self._args)
        try:
            LOG.debug(f'Running command {" ".join(cmd)}')
            process = subprocess.run(cmd, capture_output=True, text=True,
                                     check=True)
            LOG.debug(f'Command finished. stdout={process.stdout}, '
                      'stderr={process.stderr}')
            return Result(ResultType.COMPLETED)
        except subprocess.CalledProcessError as e:
            error_message = f'Error enabling microk8s add-on {self._addon}'
            LOG.exception(error_message)
            LOG.error(e.stderr)
            return Result(ResultType.FAILED, error_message)


class EnableHighAvailability(BaseCoreMicroK8sEnableStep):
    """Enables high availability for the Microk8s cluster."""
    def __init__(self):
        """Enables high availability for the microk8s cluster"""
        super().__init__('ha-cluster')


class EnableDNS(BaseCoreMicroK8sEnableStep):
    """Enables the coredns addon for Microk8s"""
    def __init__(self):
        super().__init__('dns')


class EnableStorage(BaseCoreMicroK8sEnableStep):
    """Enable host-based storage for microk8s"""
    def __init__(self):
        super().__init__('hostpath-storage')


class EnableMetalLB(BaseCoreMicroK8sEnableStep):
    """Enable metallb for microk8s"""
    def __init__(self):
        super().__init__('metallb', '10.20.20.1-10.20.20.2')


class EnableAccessToUser(BaseStep):
    """Enable microk8s access to user"""
    def __init__(self, user: str):
        super().__init__(name='Ensure microk8s access',
                         description='Provide microk8s access to user')
        self.user = user

    def is_skip(self):
        """Determines if the step should be skipped or not.

        :return: True if the Step should be skipped, False otherwise
        """
        # Check if user is already part of group
        return False

    def run(self):
        """Add user to snap_microk8s group

        """
        cmd = ['usermod', '-a', '-G', 'snap_microk8s', self.user]

        try:
            LOG.debug(f'Running command {" ".join(cmd)}')
            process = subprocess.run(cmd, capture_output=True, text=True,
                                     check=True)
            LOG.debug(f'Command finished. stdout={process.stdout}, '
                      'stderr={process.stderr}')
            return Result(ResultType.COMPLETED)
        except subprocess.CalledProcessError as e:
            error_message = 'Adding user to snap_microk8s group failed'
            LOG.exception(error_message)
            LOG.error(e.stderr)
            return Result(ResultType.FAILED, error_message)
