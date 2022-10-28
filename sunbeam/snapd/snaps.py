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

import typing
from datetime import datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

from sunbeam.snapd import service


class SnapAction(Enum):
    """Actions to take on a snap"""

    Install = "install"
    Refresh = "refresh"
    Remove = "remove"
    Revert = "revert"
    Enable = "enable"
    Disable = "disable"
    Switch = "switch"


class AppAction(Enum):
    """Actions to take on app"""

    Stop = "stop"
    Start = "start"
    Restart = "restart"


class SnapStatus(Enum):
    """Status of the snap"""

    Installed = "installed"
    Active = "active"


class App(BaseModel):
    snap: str
    name: str


class Snap(BaseModel):
    """Represents a snap package and its properties

    A snap has several properties about it, and this only capture some of them.
    """

    name: str
    apps: typing.List[App]
    channel: str
    confinement: str
    description: str
    developer: str
    devmode: bool
    icon: typing.Optional[str]
    id: str
    install_date: typing.Optional[datetime] = Field(alias="spawn-time", default=None)
    installed_size: int = Field(alias="installed-size", default=None)
    license: typing.Optional[str] = None
    private: bool
    resource: typing.Optional[str] = None
    revision: int
    status: str
    summary: str
    trymode: typing.Optional[bool] = False
    type: str
    version: str
    update_available: typing.Optional[int] = Field(
        alias="update-available", default=None
    )
    broken: typing.Optional[str] = None
    jailmode: bool
    mounted_from: Path = Field(alias="mounted-from", default=None)
    status: SnapStatus
    tracking_channel: str = Field(alias="tracking-channel", default=None)


class SnapService(service.BaseService):
    """Lists and manages installed snaps"""

    def get_installed_snaps(
        self, snaps: typing.Iterable[str] = None
    ) -> typing.List[Snap]:
        """Returns a list of Installed Snaps

        :param snaps:
        :return:
        """
        query = {}
        if snaps:
            query = {"snaps": ",".join(snaps)}

        snaps = self._get("/v2/snaps", params=query)

        installed = []
        for result in snaps["result"]:
            installed.append(Snap(**result))

        return installed

    def get_apps(self, snaps: typing.Iterable[str] = None) -> dict:
        """Returns a list of apps

        Get list of apps for the given snaps. If snap
        is None, list all apps.

        :param snaps: comma separated list of snaps
        :type snaps: str
        :return: list of apps
        :type: list
        """
        query = {}
        if snaps:
            query = {"names": ",".join(snaps)}

        services = []
        apps = self._get("/v2/apps", params=query)
        for result in apps["result"]:
            services.append(App(**result))

        return services

    def install(self, name: str, channel: typing.Optional[str] = "", **kwargs) -> int:
        """Installs the specified snap from the default (or specified) channel.

        By default, the default channel of the snap is installed. This can be
        explicitly determined by specifying the channel[/track[/risk]],
        e.g. channel='yoga/edge'.

        Additional arguments can be provided through the **kwargs argument that
        will be provided to the snapd API itself. These arguments may include
        parameters defined in the published snapd API, including but not
        limited to the following options:

        - classic: when True will install the snap in classic mode
        - devmode: when True will install the snap in developer mode
        - ignore-validation: ignore validation by other snaps blocking
                             the refresh if true
        - (and others, check https://snapcraft.io/docs/snapd-api)

        For example, the following code installs the 'hello' snap from the
        `latest/edge` channel in devmode:

            snap_service.install('hello', channel='latest/edge',
                                 devmode=True)

        :param name: the name of the snap to install
        :type: str
        :param channel: optional string specifying the channel[/track[/risk]]
                        to install the snap from
        :return: the change id used to track the status of the asynchronous
                 action
        :rtype: int
        """
        return self._update_snap(SnapAction.Install, name, channel, **kwargs)

    def remove(self, name: str, purge: bool = False) -> int:
        """Removes an installed snap from the system.

        Remove the installed snap from the system. By default, this will save a
        snapshot of the user data directory. To remove this directory as well,
        specify purge=True.

        :param name: the name of the snap to remove
        :type name: str
        :param purge: whether to purge the snapshot data
        :type purge: bool
        :return: a change id to monitor the asynchronous status
        rtype: int
        """
        kwargs = {
            "purge": purge,
        }
        return self._update_snap(SnapAction.Remove, name, **kwargs)

    def start_apps(self, names: list, **kwargs) -> int:
        """Start list of apps or all apps in a snap.

        Start the apps specified in names. If snap is specified
        in names, start all the apps in the snap.

        :param names: name of app or snap
        :type names: list
        :return: a change id to monitor the asynchronous status
        :rtype: int
        """
        return self._update_app(AppAction.Start, names, **kwargs)

    def stop_apps(self, names: list, **kwargs) -> int:
        """Stop list of apps or all apps in a snap.

        Stop the apps specified in names. If snap is specified
        in names, stop all the apps in the snap.

        :param names: name of app or snap
        :type names: list
        :return: a change id to monitor the asynchronous status
        :rtype: int
        """
        return self._update_app(AppAction.Stop, names, **kwargs)

    def restart_apps(self, names: list, **kwargs) -> int:
        """Restart list of apps or all apps in a snap.

        Restart the apps specified in names. If snap is specified
        in names, restart all the apps in the snap.

        :param names: name of app or snap
        :type names: list
        :return: a change id to monitor the asynchronous status
        :rtype: int
        """
        return self._update_app(AppAction.Restart, names, **kwargs)

    def _update_snap(
        self,
        action: SnapAction,
        name: str,
        channel: typing.Optional[str] = "",
        **kwargs,
    ) -> bool:
        data = {
            "action": str(SnapAction.Install.value),
            "channel": channel,
        }
        data.update(kwargs)

        response = self._post(f"/v2/snaps/{name}", json=data)
        change_id = response["change"]

        return change_id

    def _update_app(
        self,
        action: AppAction,
        names: list,
        **kwargs,
    ) -> bool:
        data = {
            "action": str(action.value),
            "names": names,
        }
        data.update(kwargs)

        response = self._post("/v2/apps", json=data)
        change_id = response["change"]

        return change_id
