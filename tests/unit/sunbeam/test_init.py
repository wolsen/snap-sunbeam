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

import unittest

from sunbeam.commands.init import Role


class TestRoles(unittest.TestCase):
    def test_is_control(self):
        self.assertTrue(Role.CONTROL.is_control_node())
        self.assertFalse(Role.COMPUTE.is_control_node())
        self.assertTrue(Role.CONVERGED.is_control_node())

    def test_is_compute(self):
        self.assertFalse(Role.CONTROL.is_compute_node())
        self.assertTrue(Role.COMPUTE.is_compute_node())
        self.assertTrue(Role.CONVERGED.is_compute_node())


if __name__ == "__main__":
    unittest.main()
