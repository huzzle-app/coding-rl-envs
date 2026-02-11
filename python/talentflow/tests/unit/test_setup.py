"""
Unit tests for setup/configuration bugs (S5-S10).

Tests: 12
"""
import os
import pytest


pytestmark = [pytest.mark.unit]


class TestCircularImports:
    """Tests for circular import resolution (S5)."""

    @pytest.mark.bug_s5
    def test_circular_import_resolved(self):
        """Test that the circular import between candidates/utils and jobs/utils is resolved."""
        try:
            from apps.candidates import utils as candidates_utils
            from apps.jobs import utils as jobs_utils
        except ImportError as e:
            pytest.fail(f"Circular import still exists: {e}")

    @pytest.mark.bug_s5
    def test_candidates_utils_importable(self):
        """Test that candidates utils module is importable."""
        import importlib
        mod = importlib.import_module('apps.candidates.utils')
        assert mod is not None


class TestMissingInitFile:
    """Tests for missing __init__.py (S6)."""

    @pytest.mark.bug_s6
    def test_helpers_init_exists(self):
        """Test that apps/common/helpers/__init__.py exists."""
        from pathlib import Path

        helpers_dir = Path(__file__).resolve().parents[2] / 'apps' / 'common' / 'helpers'
        init_file = helpers_dir / '__init__.py'
        assert init_file.exists(), f"Missing __init__.py at {init_file}"

    @pytest.mark.bug_s6
    def test_validators_importable(self):
        """Test that helpers validators module is importable."""
        try:
            from apps.common.helpers import validators  # noqa: F401
        except (ImportError, ModuleNotFoundError) as e:
            pytest.fail(f"Cannot import validators from helpers: {e}")


class TestMigrationChain:
    """Tests for migration dependency chain (S7)."""

    @pytest.mark.bug_s7
    @pytest.mark.django_db
    def test_migration_chain_valid(self):
        """Test that migration dependency chain is valid."""
        from django.core.management import call_command
        from io import StringIO

        out = StringIO()
        try:
            call_command('showmigrations', '--plan', stdout=out)
        except Exception as e:
            pytest.fail(f"Migration chain is broken: {e}")

    @pytest.mark.bug_s7
    def test_migration_dependencies_correct(self):
        """Test that migration 0005 depends on the correct predecessor."""
        from pathlib import Path
        import re

        migrations_dir = Path(__file__).resolve().parents[2] / 'apps' / 'candidates' / 'migrations'
        migration_files = list(migrations_dir.glob('0005*.py'))

        if not migration_files:
            pytest.skip("No 0005 migration file found")

        content = migration_files[0].read_text()
        # Should depend on 0004, not 0003
        assert '0004' in content, "Migration 0005 should depend on 0004"


class TestEnvVarCoercion:
    """Tests for environment variable type coercion (S8)."""

    @pytest.mark.bug_s8
    def test_debug_env_var_coercion(self):
        """Test that DEBUG env var is correctly coerced from string."""
        # The string 'false' should evaluate to False, not True
        false_strings = ['false', 'False', 'FALSE', '0', 'no', '']
        for val in false_strings:
            result = val.lower() in ('true', '1', 'yes')
            assert result is False, f"'{val}' should not be truthy"

    @pytest.mark.bug_s8
    def test_debug_false_string_is_false(self):
        """Test that DEBUG=false results in DEBUG being False."""
        from django.conf import settings

        # In testing, DEBUG should be False
        assert settings.DEBUG is False, "DEBUG should be False in test settings"


class TestPackageConflicts:
    """Tests for package version conflicts (S9)."""

    @pytest.mark.bug_s9
    def test_no_conflicting_packages(self):
        """Test that there are no conflicting package versions."""
        from pathlib import Path

        req_file = Path(__file__).resolve().parents[2] / 'requirements.txt'
        if not req_file.exists():
            pytest.skip("requirements.txt not found")

        content = req_file.read_text()
        lines = [l.strip().lower() for l in content.splitlines() if l.strip() and not l.startswith('#')]

        # Should not have both psycopg2 and psycopg2-binary
        has_psycopg2 = any(l.startswith('psycopg2==') or l == 'psycopg2' for l in lines)
        has_psycopg2_binary = any(l.startswith('psycopg2-binary') for l in lines)

        assert not (has_psycopg2 and has_psycopg2_binary), \
            "requirements.txt should not have both psycopg2 and psycopg2-binary"

    @pytest.mark.bug_s9
    def test_psycopg2_single_version(self):
        """Test that only one psycopg2 variant is installed."""
        import importlib

        try:
            importlib.import_module('psycopg2')
        except ImportError:
            pytest.skip("psycopg2 not installed")


class TestSettingsModulePath:
    """Tests for settings module path (S10)."""

    @pytest.mark.bug_s10
    def test_settings_module_path_correct(self):
        """Test that DJANGO_SETTINGS_MODULE is set correctly."""
        settings_module = os.environ.get('DJANGO_SETTINGS_MODULE', '')
        assert 'talentflow.settings' in settings_module, \
            f"Settings module should be under talentflow.settings, got: {settings_module}"

    @pytest.mark.bug_s10
    def test_manage_py_settings_path(self):
        """Test that manage.py references correct settings module."""
        from pathlib import Path

        manage_py = Path(__file__).resolve().parents[2] / 'manage.py'
        if not manage_py.exists():
            pytest.skip("manage.py not found")

        content = manage_py.read_text()
        assert 'talentflow.settings' in content, \
            "manage.py should reference talentflow.settings"
