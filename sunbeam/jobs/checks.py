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
from typing import List

from snaphelpers import Snap

from sunbeam.snapd.client import Client as SnapClient

LOG = logging.getLogger(__name__)


class Check:
    """Base class for Pre-flight checks.

    Check performs a verification step to determine
    to proceed further or not.
    """

    def __init__(self, name: str, description: str = ""):
        """Initialise the Check.

        :param name: the name of the check
        """
        self.name = name
        self.description = description
        self.message = None

    def run(self) -> bool:
        """Run the check logic here.

        Return True if check is Ok.
        Otherwise update self.message and return False.
        """

        return True


class MissingSnapsCheck(Check):
    """Check if pre-requisite snaps are not installed."""

    def __init__(self, snaps: List[str]):
        super().__init__(
            "Check missing snaps", "Checking pre-requisites: necessary snaps installed"
        )
        self.snaps = snaps

    def run(self) -> bool:
        """Check if all provided snaps are installed."""

        snap_client = SnapClient()
        installed_snaps = snap_client.snaps.get_installed_snaps(self.snaps)
        installed_snaps = [snap.name for snap in installed_snaps]
        missing_snaps = set(self.snaps) - set(installed_snaps)
        if missing_snaps:
            self.message = (
                "Missing pre-requisites: Install the following snaps:  "
                f"{missing_snaps}."
            )
            return False

        return True


class ConnectJujuSlotCheck(Check):
    """Check if juju content is connected or not."""

    def __init__(self):
        super().__init__(
            "Check juju content", "Checking pre-requisites: snap connection juju-bin"
        )

    def run(self) -> bool:
        """Check if all provided snaps are installed."""

        snap = Snap()
        juju_content = snap.paths.snap / "juju"
        if not juju_content.exists():
            self.message = (
                "Run the following command to connect microstack and juju: \n"
                "sudo snap connect microstack:juju-bin juju:juju-bin"
            )

            return False

        return True
