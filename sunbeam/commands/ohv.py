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
import operator
from typing import Optional

from sunbeam.commands.juju import JujuHelper
from sunbeam.jobs.common import BaseStep, Result, ResultType
from sunbeam.ohv_config.client import Client as ohvClient
from sunbeam.ohv_config.config import RabbitMQConfig

LOG = logging.getLogger(__name__)


class OHVBaseStep(BaseStep):
    def __init__(self, name: str, description: str):
        super().__init__(name, description)

        self.ohv_client = ohvClient()
        self.action_result = asyncio.get_event_loop().run_until_complete(
            JujuHelper.run_action(self.app, self.action_cmd, self.action_params)
        )
        LOG.debug(
            f"Action result for app {self.app} action {self.action_cmd} "
            f"with params {self.action_params}: {self.action_result}"
        )

    def is_skip(self, status: Optional["Status"] = None):
        """Determines if the step should be skipped or not.

        :return: True if the Step should be skipped, False otherwise
        """
        config_func = getattr(self.ohv_client.config, self.get_config_func_name)
        config_from_snap = config_func()
        LOG.debug(f"Config from openstack-hypervisor snap: {config_from_snap}")

        if operator.eq(self.config.dict(), config_from_snap.dict()):
            return True

        return False

    def run(self, status: Optional["Status"] = None) -> Result:
        """Run the step to completion.

        Invoked when the step is run and returns a ResultType to indicate

        :return:
        """
        try:
            config_func = getattr(self.ohv_client.config, self.update_config_func_name)
            result = config_func(self.config)
            LOG.debug(f"Result after updating rabbitmq config: {result}")
        except Exception as e:
            LOG.exception("Error setting config for openstack-hypervisor")
            return Result(ResultType.FAILED, str(e))

        return Result(ResultType.COMPLETED)


class UpdateRabbitMQConfigStep(OHVBaseStep):
    """Update Rabbitmq Config for openstack-hypervisor snap"""

    def __init__(self):
        self.app = "rabbitmq"
        self.action_cmd = "get-service-account"
        self.action_params = {"username": "nova", "vhost": "openstack"}
        self.get_config_func_name = "get_rabbitmq_config"
        self.update_config_func_name = "update_rabbitmq_config"

        super().__init__(
            "Update Rabbitmq Config", "Update rabbitmq url to openstack-hypervisor snap"
        )

        self.config = RabbitMQConfig(**self.action_result)
