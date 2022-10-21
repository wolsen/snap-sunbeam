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

from pathlib import Path

import requests
import requests_unixsocket

from sunbeam.ohv_config.config import ConfigService


class Client:
    """A client for interacting with the remote client API."""

    def __init__(self, version: str = "v2", socket_path: Path = "/run/snapd.socket"):
        super(Client, self).__init__()
        self.__version = version
        self.__socket_path = socket_path
        self._session = requests.sessions.Session()
        self._session.mount(
            requests_unixsocket.DEFAULT_SCHEME, requests_unixsocket.UnixAdapter()
        )
        self.config = ConfigService(self._session)
