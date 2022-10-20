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
import os
from typing import Optional

from sunbeam.commands.juju import JujuHelper
from sunbeam.jobs.common import BaseStep, Result, ResultType
from sunbeam.ohv_config.client import Client as ohvClient
from sunbeam.ohv_config.config import RabbitMQConfig

LOG = logging.getLogger(__name__)


class OHVBaseStep(BaseStep):
    def __init__(self, name: str, description: str):
        super().__init__(name, description)

        home = os.environ.get("SNAP_REAL_HOME")
        os.environ["JUJU_DATA"] = f"{home}/.local/share/juju"

        self.ohv_client = ohvClient()
        self.action_result = asyncio.get_event_loop().run_until_complete(
            JujuHelper.run_action(self.app, self.action_cmd, self.action_params)
        )
        LOG.debug(
            f"Action result for app {self.app} action {self.action_cmd} "
            f"with params {self.action_params}: {self.action_result}"
        )


class UpdateRabbitMQConfigStep(OHVBaseStep):
    """Update Rabbitmq Config for openstack-hypervisor snap"""

    def __init__(self):
        self.app = "rabbitmq"
        self.action_cmd = "get-service-account"
        self.action_params = {"username": "nova", "vhost": "openstack"}

        super().__init__(
            "Update Rabbitmq Config", "Update rabbitmq url to openstack-hypervisor snap"
        )

        self.config = RabbitMQConfig(**self.action_result)

    def is_skip(self, status: Optional["Status"] = None):
        """Determines if the step should be skipped or not.

        :return: True if the Step should be skipped, False otherwise
        """
        mq_conf = self.ohv_client.config.get_rabbitmq_config()
        LOG.debug(f"Config from openstack-hypervisor snap: {mq_conf}")

        # Compare self.config and mq_conf, can comparision method be
        # pushed to ohv_config/config.py??
        return False

    def run(self, status: Optional["Status"] = None) -> Result:
        """Run the step to completion.

        Invoked when the step is run and returns a ResultType to indicate

        :return:
        """
        result = self.ohv_client.config.update_rabbitmq_config(self.config)
        # TODO(hemanth): Is result dict? Any exceptions to be handler here?
        LOG.debug(f"Result after updating rabbitmq config: {result}")
        return Result(ResultType.COMPLETED)
