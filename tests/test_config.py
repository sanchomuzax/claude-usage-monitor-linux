"""Unit tests for config.py — settings and credential loading."""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import config as cfg


# ------------------------------------------------------------------ #
#  Settings                                                             #
# ------------------------------------------------------------------ #

class TestLoadSettings:
    def test_defaults_when_no_file(self, tmp_path):
        with patch.object(cfg, "SETTINGS_PATH", tmp_path / "nonexistent.json"):
            settings = cfg.load_settings()
        assert settings.poll_interval_minutes == 15
        assert settings.x == 100
        assert settings.y == 100
        assert settings.theme == "auto"

    def test_loads_saved_values(self, tmp_path):
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(
            json.dumps({"poll_interval_minutes": 5, "x": 200, "y": 300, "theme": "dark"})
        )
        with patch.object(cfg, "SETTINGS_PATH", settings_file):
            settings = cfg.load_settings()
        assert settings.poll_interval_minutes == 5
        assert settings.x == 200
        assert settings.y == 300
        assert settings.theme == "dark"

    def test_partial_overrides_use_defaults(self, tmp_path):
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(json.dumps({"x": 500}))
        with patch.object(cfg, "SETTINGS_PATH", settings_file):
            settings = cfg.load_settings()
        assert settings.x == 500
        assert settings.poll_interval_minutes == 15  # default

    def test_corrupt_file_returns_defaults(self, tmp_path):
        settings_file = tmp_path / "settings.json"
        settings_file.write_text("not valid json {{")
        with patch.object(cfg, "SETTINGS_PATH", settings_file):
            settings = cfg.load_settings()
        assert settings.poll_interval_minutes == 15


class TestSaveSettings:
    def test_round_trip(self, tmp_path):
        settings_file = tmp_path / "settings.json"
        settings_dir = tmp_path
        original = cfg.Settings(poll_interval_minutes=30, x=400, y=50, theme="light")
        with (
            patch.object(cfg, "SETTINGS_DIR", settings_dir),
            patch.object(cfg, "SETTINGS_PATH", settings_file),
        ):
            cfg.save_settings(original)
            loaded = cfg.load_settings()
        assert loaded.poll_interval_minutes == 30
        assert loaded.x == 400
        assert loaded.y == 50
        assert loaded.theme == "light"

    def test_creates_parent_directory(self, tmp_path):
        nested = tmp_path / "a" / "b" / "settings.json"
        nested_dir = tmp_path / "a" / "b"
        settings = cfg.Settings()
        with (
            patch.object(cfg, "SETTINGS_DIR", nested_dir),
            patch.object(cfg, "SETTINGS_PATH", nested),
        ):
            cfg.save_settings(settings)
        assert nested.exists()


# ------------------------------------------------------------------ #
#  Credentials loading                                                  #
# ------------------------------------------------------------------ #

class TestLoadOauthToken:
    def test_no_credentials_file_returns_none(self, tmp_path):
        with patch.object(cfg, "CREDENTIALS_PATH", tmp_path / "missing.json"):
            assert cfg.load_oauth_token() is None

    def test_string_token(self, tmp_path):
        creds = tmp_path / "credentials.json"
        creds.write_text(json.dumps({"claudeAiOauth": "my-token-123"}))
        with patch.object(cfg, "CREDENTIALS_PATH", creds):
            assert cfg.load_oauth_token() == "my-token-123"

    def test_dict_token_with_access_token(self, tmp_path):
        creds = tmp_path / "credentials.json"
        creds.write_text(json.dumps({
            "claudeAiOauth": {"accessToken": "bearer-abc", "refreshToken": "refresh-xyz"}
        }))
        with patch.object(cfg, "CREDENTIALS_PATH", creds):
            assert cfg.load_oauth_token() == "bearer-abc"

    def test_missing_claude_ai_oauth_key_returns_none(self, tmp_path):
        creds = tmp_path / "credentials.json"
        creds.write_text(json.dumps({"someOtherKey": "value"}))
        with patch.object(cfg, "CREDENTIALS_PATH", creds):
            assert cfg.load_oauth_token() is None

    def test_corrupt_file_returns_none(self, tmp_path):
        creds = tmp_path / "credentials.json"
        creds.write_text("{ bad json")
        with patch.object(cfg, "CREDENTIALS_PATH", creds):
            assert cfg.load_oauth_token() is None
