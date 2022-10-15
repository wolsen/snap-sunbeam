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

import enum
import logging
import typing


LOG = logging.getLogger(__name__)


class ResultType(enum.Enum):
    COMPLETED = 0
    FAILED = 1
    SKIPPED = 2


class Result:
    """The result of running a step

    """

    def __init__(self, result_type: ResultType,
                 message: typing.Optional[str] = ''):
        """Creates a new result

        :param result_type:
        :param message:
        """
        self.result_type = result_type
        self.message = message


class StepResult:
    """The Result of running a Step.

    The results of running contain the minimum of the ResultType to indicate
    whether running the Step was completed, failed, or skipped.
    """

    def __init__(self, result_type: ResultType = ResultType.COMPLETED,
                 **kwargs):
        """Creates a new StepResult.

        The StepResult will contain various information regarding the result
        of running a Step. By default, a new StepResult will be created with
        result_type set to ResultType.COMPLETED.

        Additional attributes can be stored in the StepResult object by using
        the kwargs values, but the keys must be unique to the StepResult
        already. If the kwargs contains a keyword that is an attribute on the
        object then a ValueError is raised.

        :param result_type: the result of running a plan or step.
        :param kwargs: additional attributes to store in the step.
        :raises: ValueError if a key in the kwargs already exists on the
                 object.
        """
        self.result_type = result_type
        for key, value in kwargs.items():
            # Note(wolsen) this is a bit of a defensive check to make sure
            # a bit of code doesn't accidentally override a base object
            # attribute.
            if hasattr(self, key):
                raise ValueError(f'{key} was specified but already exists on '
                                 f'this StepResult.')
            self.__setattr__(key, value)


class BaseStep:
    """A step defines a logical unit of work to be done as part of a plan.

    A step determines what needs to be done in order to perform a logical
    action as part of carrying out a plan.
    """

    def __init__(self, name: str, description: str = ''):
        """Initialise the BaseStep

        :param name: the name of the step
        """
        self.name = name
        self.description = description

    def prompt(self, console: 'rich.console.Console' = None) -> None:
        """Determines if the step can take input from the user.

        Prompts are used by Steps to gather the necessary input prior to
        running the step. Steps should not expect that the prompt will be
        available and should provide a reasonable default where possible.
        """
        pass

    def is_skip(self):
        """Determines if the step should be skipped or not.

        :return: True if the Step should be skipped, False otherwise
        """
        return False

    def run(self) -> Result:
        """Run the step to completion.

        Invoked when the step is run and returns a ResultType to indicate

        :return:
        """
        pass
