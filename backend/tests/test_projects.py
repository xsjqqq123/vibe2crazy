"""
Tests for project schemas, focusing on ProjectCreate with init_git field.
"""
import pytest
from pydantic import ValidationError
from app.schemas import ProjectCreate


class TestProjectCreateInitGit:
    """Test ProjectCreate schema init_git field."""

    def test_project_create_with_init_git(self):
        """Verify ProjectCreate accepts init_git field."""
        project_data = {
            "name": "Test Project",
            "git_path": "/path/to/repo",
            "main_branch": "main",
            "init_git": True
        }

        project = ProjectCreate(**project_data)

        assert project.name == "Test Project"
        assert project.git_path == "/path/to/repo"
        assert project.main_branch == "main"
        assert project.init_git is True

    def test_project_create_init_git_defaults_to_false(self):
        """Verify init_git defaults to False when not provided."""
        project_data = {
            "name": "Test Project",
            "git_path": "/path/to/repo",
            "main_branch": "main"
        }

        project = ProjectCreate(**project_data)

        assert project.name == "Test Project"
        assert project.git_path == "/path/to/repo"
        assert project.main_branch == "main"
        assert project.init_git is False
