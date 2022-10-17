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

import time
import typing
from datetime import datetime, timedelta
from enum import Enum

from pydantic import BaseModel, Field

from sunbeam.snapd import service


class TimeoutException(Exception):
    """Raised to indicate an activity timedout while waiting for completion."""

    def __init__(self, message):
        self.message = message


class Status(Enum):
    """The status of tasks and changes.

    Refer to the following status bit in snapd for more
    https://github.com/snapcore/snapd/blob/
        a4da44a5c975f0d5c805327dd333fc1e4da0006e/overlord/state/change.go
    """

    DefaultStatus = "Default"
    DoStatus = "Do"
    DoingStatus = "Doing"
    DoneStatus = "Done"
    AbortStatus = "Abort"
    UndoStatus = "Undo"
    UndoingStatus = "Undoing"
    UndoneStatus = "Undone"
    HoldStatus = "Hold"
    ErrorStatus = "Error"


class Progress(BaseModel):
    label: str
    done: int
    total: int


class Task(BaseModel):
    """Represents a task in the snap system.

    A task is associated with a change and includes information such as what
    the current status is, what the progress information is, etc.
    """

    id: int
    kind: str
    summary: str
    status: Status
    progress: Progress
    spawn_time: typing.Optional[datetime] = Field(alias="spawn-time", default=None)
    ready_time: typing.Optional[datetime] = Field(alias="ready-time", default=None)


class Change(BaseModel):
    """Represents a change in the snap system.

    A Change records a change within the snap system including what tasks
    were being performed by the changed, when the change was initiated, its
    status, etc.
    """

    id: int
    kind: str
    summary: str
    status: Status
    tasks: typing.List[Task]
    ready: bool
    spawn_time: typing.Optional[datetime] = Field(alias="spawn-time", default=None)


class ChangeService(service.BaseService):
    """Lists and manages snap changes"""

    def get_status(self, change: typing.Union[Change, int]) -> Change:
        """Retrieves the current status of a change/change id.

        :param change: the change or change id to get the current status of
        :type change: Change or int. If a change is provided, the change.id
                      will be used to query the status
        :return: Change status
        :rtype: Change
        """
        change_id = change.id if isinstance(change, Change) else change
        change_data = self._get(f"/v2/changes/{change_id}")
        change_data = change_data["result"]

        return Change(**change_data)

    def wait_until(
        self,
        change: typing.Union[Change, int],
        status: typing.Optional[
            typing.Union[Status, typing.Iterable[Status]]
        ] = Status.DoneStatus,
        timeout: typing.Optional[int] = 180,
        sleep_time: typing.Optional[int] = 1,
    ) -> None:
        """Waits until the change is in the specified target status.

        This will only watch the specific change id, not any of the individual
        subtasks that make up the change.

        :param change: the Change or change id of the change to wait for
        :type change: Change or int
        :param status: the target status the change should reach
        :type status: a Status or Iterable of Statuses
        :param timeout: the amount of time to wait for the task to complete,
                        specified in seconds. (Default 60 seconds.)
        :type timeout: int
        :param sleep_time: the amount of time to sleep between queries of
                           updated status, specified in seconds.
                           (Default 1 second.)
        :type sleep_time: int
        :return: None
        :raises: TimeoutException if the change does not transition to one of
                 the desired states within the timeout window
        """
        # Make it iterable for ease
        if isinstance(status, Status):
            status = [status]

        change_id = change.id if isinstance(change, Change) else change
        start = now = datetime.now()
        end = start + timedelta(seconds=timeout)

        while now < end:
            change = self.get_status(change)
            if change.status in status:
                return

            sleep_time = min(sleep_time, (end - now).seconds)
            time.sleep(sleep_time)

            now = datetime.now()

        if len(status) > 1:
            tgt_msg = f'one of {", ".join(status)}'  # noqa
        else:
            tgt_msg = status[0]

        raise TimeoutException(
            f"Timed out after {timeout} seconds waiting "
            f"for change {change_id} to reach "
            f"{tgt_msg}"
        )
