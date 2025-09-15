import pytest
import json
from pathlib import Path
from unittest.mock import patch, mock_open

from core.config.exceptions import UnexpectedError
from core.personalities import PersonalityManager


def test_load_personalities_success():
    data = [{"name": "Cheerful"}, {"name": "Serious"}]
    m = mock_open(read_data=json.dumps(data))
    with patch("builtins.open", m):
        pm = PersonalityManager(file_path=Path("fake_path.json"))
        assert pm._personalities == data


def test_get_random_personality():
    data = [{"name": "Cheerful"}, {"name": "Serious"}]
    m = mock_open(read_data=json.dumps(data))
    with patch("builtins.open", m):
        pm = PersonalityManager(file_path=Path("fake_path.json"))
        choice = pm.get_random_personality()
        assert choice in data


def test_load_personalities_file_not_found():
    with patch("builtins.open", side_effect=FileNotFoundError):
        with pytest.raises(UnexpectedError):
            PersonalityManager(file_path=Path("missing.json"))


def test_load_personalities_invalid_json():
    m = mock_open(read_data="{invalid_json}")
    with patch("builtins.open", m):
        with pytest.raises(UnexpectedError):
            PersonalityManager(file_path=Path("bad.json"))


def test_get_random_personality_empty_list():
    m = mock_open(read_data="[]")
    with patch("builtins.open", m):
        pm = PersonalityManager(file_path=Path("empty.json"))
        with pytest.raises(UnexpectedError):
            pm.get_random_personality()
