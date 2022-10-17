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

from semver import VersionInfo

from sunbeam import utils


class UtilsTestCase(unittest.TestCase):
    def test_juju_version_parsing_beta(self):
        version = utils.parse_version("3.1-beta1-865f83e")
        expected = VersionInfo(3, 1, 0, "beta1")
        self.assertEqual(version, expected)

    def test_juju_version_parsing_rc(self):
        version = utils.parse_version("3.0-rc1")
        expected = VersionInfo(3, 0, 0, "rc1")
        self.assertEqual(version, expected)

    def test_juju_other_versions(self):
        version = utils.parse_version("2.9.36-1a46655")
        expected = VersionInfo(2, 9, 36, "1a46655")
        self.assertEqual(version, expected)

    def test_microk8s_version(self):
        version = utils.parse_version("v1.25.2")
        expected = VersionInfo(1, 25, 2)
        self.assertEqual(version, expected)


if __name__ == "__main__":
    unittest.main()
