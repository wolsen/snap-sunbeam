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

from snaphelpers import Snap

from sunbeam.commands.juju import JujuHelper
from sunbeam.jobs.common import BaseStep, Result, ResultType
from sunbeam.ohv_config.client import Client as ohvClient
from sunbeam import utils

LOG = logging.getLogger(__name__)


class OHVBaseStep(BaseStep):
    def __init__(self, name: str, description: str):
        super().__init__(name, description)

        self.action_info = []
        self.action_results = []
        self.config_from_snap = None
        self.get_config_func_name = None
        self.update_config_func_name = None

        # Mapping of keys from Action result to
        # openstack-hypervisor configuration keys
        self.map_alias = {}

    def _apply_handlers(self, config: dict) -> dict:
        """Placeholder to do any special handling"""

        return config

    def _apply_action_handlers(self) -> bool:
        """Update config retrieved from juju actions"""
        skip = True

        # Get configuration from openstack control plane
        for action in self.action_info:
            app = action.get("app", None)
            action_cmd = action.get("action_cmd", None)
            action_params = action.get("action_params", {})
            map_alias = action.get("map_alias", {})
            attributes_to_update = action.get("attributes_to_update", [])

            action_result = asyncio.get_event_loop().run_until_complete(
                asyncio.gather(JujuHelper.run_action(app, action_cmd, action_params))
            )
            if isinstance(action_result, list):
                action_result = action_result[0]

            LOG.debug(
                f"Action result for app {app} action {action_cmd} "
                f"with params {action_params}: {action_result}"
            )

            # The keys from action result dict and openstack-hypervisor config
            # might be diferent, so add the mapping keys to action result
            # For eg.,if action_result returns 'public-endpoint':'http://localhost:1234'
            # and corresponding openstack-hypervisor key is auth-url, add
            # 'auth-url':'http://localhost:1234' to the action result.
            missing_keys = {
                v: action_result[k] for k, v in map_alias.items() if k in action_result
            }
            action_result.update(missing_keys)
            LOG.debug(f"Config after adding {missing_keys}: {action_result}")

            action_result = self._apply_handlers(action_result)
            LOG.debug(f"Config after applying handlers: {action_result}")
            self.action_results.append(action_result)

            for attribute in attributes_to_update:

                value_from_action = action_result.get(attribute, None)
                value_from_config = vars(self.config_from_snap).get(attribute, None)
                if not operator.eq(value_from_config, value_from_action):
                    setattr(
                        self.config_from_snap,
                        attribute.replace("-", "_"),
                        value_from_action,
                    )
                    skip = False

        return skip

    def is_skip(self, status: Optional["Status"] = None):
        """Determines if the step should be skipped or not.

        :return: True if the Step should be skipped, False otherwise
        """
        skip = True

        # Get configuration from openstack-hypervisor snap
        self.ohv_client = ohvClient()
        get_config_func = getattr(self.ohv_client.config, self.get_config_func_name)
        self.config_from_snap = get_config_func()
        LOG.debug(f"Config from openstack-hypervisor snap: {self.config_from_snap}")

        skip = self._apply_action_handlers()

        LOG.debug(
            f"Config to apply on openstack-hypervisor snap: " f"{self.config_from_snap}"
        )
        return skip

    def run(self, status: Optional["Status"] = None) -> Result:
        """Run the step to completion.

        Invoked when the step is run and returns a ResultType to indicate

        :return:
        """
        for action_result in self.action_results:
            if action_result.get("return-code", 1) == 1:
                return Result(ResultType.FAILED, "Juju action returned error")

        try:
            config_func = getattr(self.ohv_client.config, self.update_config_func_name)
            result = config_func(self.config_from_snap)
            LOG.debug(f"Result after updating rabbitmq config: {result}")
        except Exception as e:
            LOG.exception("Error setting config for openstack-hypervisor")
            return Result(ResultType.FAILED, str(e))

        return Result(ResultType.COMPLETED)


class UpdateIdentityServiceConfigStep(OHVBaseStep):
    """Update Identity config for openstack-hypervisor snap"""

    def __init__(self):
        super().__init__(
            "Update Identity Config",
            "Update identity settings to openstack-hypervisor snap",
        )

        hostname = utils.get_hostname()
        self.action_info = [
            {
                "app": "keystone",
                "action_cmd": "get-service-account",
                # TODO(hemanth): Username should be modified with hostname of
                # each hypervisor prefixed with nova-
                "action_params": {"username": hostname},
                "map_alias": {"public-endpoint": "auth-url", "region": "region_name"},
                "attributes_to_update": {
                    "auth-url",
                    "username",
                    "password",
                    "user-domain-name",
                    "project-name",
                    "project-domain-name",
                    "region_name",
                },
            }
        ]

        self.get_config_func_name = "get_identity_config"
        self.update_config_func_name = "update_identity_config"


class UpdateRabbitMQConfigStep(OHVBaseStep):
    """Update Rabbitmq Config for openstack-hypervisor snap"""

    def __init__(self):
        super().__init__(
            "Update Rabbitmq Config", "Update rabbitmq url to openstack-hypervisor snap"
        )

        self.action_info = [
            {
                "app": "rabbitmq",
                "action_cmd": "get-service-account",
                "action_params": {"username": "nova", "vhost": "openstack"},
                "map_alias": {},
                "attributes_to_update": {"url"},
            }
        ]

        self.get_config_func_name = "get_rabbitmq_config"
        self.update_config_func_name = "update_rabbitmq_config"


class UpdateNetworkConfigStep(OHVBaseStep):
    """Update Network Config for openstack-hypervisor snap"""

    def __init__(self):
        super().__init__(
            "Update Network Config", "Update ovn-sb url to openstack-hypervisor snap"
        )

        snap = Snap()

        # TODO(hemanth): cn needs to be updated from cluster
        sans = ""
        cn = utils.get_hostname()
        compute_sans = snap.config.get("compute.sans")
        if cn in compute_sans:
            sans = compute_sans[cn]

        self.action_info = [
            {
                "app": "ovn-relay",
                "action_cmd": "get-southbound-db-url",
                "action_params": {},
                "map_alias": {"url": "ovn-sb-connection"},
                "attributes_to_update": ["ovn-sb-connection"],
            },
            {
                "app": "vault",
                "action_cmd": "generate-certificate",
                "action_params": {
                    "cn": cn,
                    "sans": sans,
                    "type": "client",
                },
                "map_alias": {
                    "private-key": "ovn-key",
                    "certificate": "ovn-cert",
                    "issuing-ca": "ovn-cacert",
                },
                "attributes_to_update": ["ovn-key", "ovn-cert", "ovn-cacert"],
            },
        ]

        self.get_config_func_name = "get_network_config"
        self.update_config_func_name = "update_network_config"

    def _apply_handlers(self, config: dict) -> dict:
        """Encode TLS certs and keys"""

        if "ovn-key" in config:
            config["ovn-key"] = utils.encode_tls(config["ovn-key"])
        if "ovn-cert" in config:
            config["ovn-cert"] = utils.encode_tls(config["ovn-cert"])
        if "ovn-cacert" in config:
            config["ovn-cacert"] = utils.encode_tls(config["ovn-cacert"])

        return config
