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

import pathlib
import tempfile
import unittest
from unittest.mock import patch

import yaml

import sunbeam.commands.question_helper as question_helper


def MockPrompt(question, default=None, console=None, choices=None):
    return default


class MockQuestion(question_helper.Question):
    """Ask the user a question."""

    @property
    def question_function(self):
        return MockPrompt


def mock_password_generator():
    return "password"


questions = {
    "username": MockQuestion(
        "Username to use for access to OpenStack", default_value="demo"
    ),
    "password": MockQuestion(
        "Password for user", default_function=mock_password_generator
    ),
}


class TestQuestionHelpers(unittest.TestCase):
    def test_quesion(self):
        user_questions = question_helper.QuestionBank(
            questions=questions,
            console=None,
            preseed={},
            previous_answers={},
        )
        self.assertEqual(user_questions.username.ask(), "demo")

    def test_quesion_preseed(self):
        user_questions = question_helper.QuestionBank(
            questions=questions,
            console=None,
            preseed={"username": "preseed_user"},
            previous_answers={},
        )
        self.assertEqual(user_questions.username.ask(), "preseed_user")

    def test_quesion_previous(self):
        user_questions = question_helper.QuestionBank(
            questions=questions,
            console=None,
            preseed={},
            previous_answers={"username": "previous_user"},
        )
        self.assertEqual(user_questions.username.ask(), "previous_user")

    def test_quesion_new_default(self):
        user_questions = question_helper.QuestionBank(
            questions=questions, console=None, preseed={}, previous_answers={}
        )
        self.assertEqual(user_questions.username.ask("special_user"), "special_user")

    def test_quesion_preseed_previous(self):
        user_questions = question_helper.QuestionBank(
            questions=questions,
            console=None,
            preseed={"username": "preseed_user"},
            previous_answers={"username": "previous_user"},
        )
        self.assertEqual(user_questions.username.ask(), "preseed_user")

    def test_quesion_preseed_new_default(self):
        user_questions = question_helper.QuestionBank(
            questions=questions,
            console=None,
            preseed={"username": "preseed_user"},
            previous_answers={},
        )
        self.assertEqual(user_questions.username.ask("special_user"), "preseed_user")

    def test_quesion_previous_new_default(self):
        user_questions = question_helper.QuestionBank(
            questions=questions,
            console=None,
            preseed={},
            previous_answers={"username": "previous_user"},
        )
        self.assertEqual(user_questions.username.ask("special_user"), "previous_user")

    def test_default_function(self):
        user_questions = question_helper.QuestionBank(
            questions=questions,
            console=None,
            preseed={},
            previous_answers={},
        )
        self.assertEqual(user_questions.password.ask(), "password")

    def test_read_preseed(self):
        test_data = {"foo": "ba"}
        with tempfile.TemporaryDirectory() as tmpdirname:
            seed_file = tmpdirname + "/seed_data.yaml"
            with open(seed_file, "w") as file:
                yaml.dump(test_data, file)
            self.assertEqual(question_helper.read_preseed(seed_file), test_data)

    def test_generate_password(self):
        self.assertTrue(len(question_helper.generate_password()) == 12)

    @patch.object(question_helper, "Snap")
    def test_manage_answer_file(self, mock_snap):
        test_data = {"foo": "ba"}
        with tempfile.TemporaryDirectory() as tmpdirname:
            answer_file = pathlib.Path(tmpdirname + "/seed_data.yaml")
            question_helper.write_answers(test_data, answer_file)
            self.assertEqual(question_helper.load_answers(answer_file), test_data)
