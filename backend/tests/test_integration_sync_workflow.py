import pytest
import subprocess
from pathlib import Path
from sqlalchemy.orm import Session
from app.models import Project, Task
from app.services.git_service import GitService


@pytest.fixture
def parallel_tasks_setup(db_session: Session, tmp_path):
    """Create project with two tasks that both modify the same file"""
    project = Project(
        id="test-project-sync",
        name="Test Sync Project",
        git_path=str(tmp_path / "repo"),
        main_branch="main"
    )
    db_session.add(project)
    db_session.commit()

    repo_path = Path(project.git_path)
    repo_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_path, capture_output=True)

    (repo_path / "shared.txt").write_text("initial content\n")
    subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_path, capture_output=True)
    subprocess.run(["git", "branch", "-M", "main"], cwd=repo_path, capture_output=True)

    worktree_a_path = tmp_path / "worktree-a"
    subprocess.run(["git", "worktree", "add", str(worktree_a_path), "-b", "task-a"], cwd=repo_path, capture_output=True)
    task_a = Task(
        id="task-a",
        project_id=project.id,
        name="Task A",
        branch_name="task-a",
        worktree_path=str(worktree_a_path),
        tmux_session="v2d-task-a",
        status="active"
    )
    db_session.add(task_a)

    worktree_b_path = tmp_path / "worktree-b"
    subprocess.run(["git", "worktree", "add", str(worktree_b_path), "-b", "task-b"], cwd=repo_path, capture_output=True)
    task_b = Task(
        id="task-b",
        project_id=project.id,
        name="Task B",
        branch_name="task-b",
        worktree_path=str(worktree_b_path),
        tmux_session="v2d-task-b",
        status="active"
    )
    db_session.add(task_b)
    db_session.commit()

    return project, task_a, task_b, repo_path


def test_parallel_tasks_sync_workflow(parallel_tasks_setup):
    """Test full workflow: Task A merges, Task B must sync with conflicts"""
    project, task_a, task_b, repo_path = parallel_tasks_setup

    # Task A modifies file
    (Path(task_a.worktree_path) / "shared.txt").write_text("task a change\n")
    subprocess.run(["git", "add", "."], cwd=task_a.worktree_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Task A change"], cwd=task_a.worktree_path, capture_output=True)

    # Task A merges to main
    success, msg, _ = GitService.squash_merge(
        repo_path=str(repo_path),
        branch_name=task_a.branch_name,
        message="Merge Task A",
        target_branch=project.main_branch
    )
    assert success is True

    # Task B modifies same file differently
    (Path(task_b.worktree_path) / "shared.txt").write_text("task b change\n")
    subprocess.run(["git", "add", "."], cwd=task_b.worktree_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Task B change"], cwd=task_b.worktree_path, capture_output=True)

    # Task B tries to sync (should detect conflicts)
    success, msg, has_conflicts, conflict_files = GitService.sync_main_into_worktree(
        worktree_path=task_b.worktree_path,
        main_branch=project.main_branch
    )

    assert has_conflicts is True
    assert len(conflict_files) > 0
    assert "shared.txt" in conflict_files

    # Simulate conflict resolution
    (Path(task_b.worktree_path) / "shared.txt").write_text("resolved content\n")
    subprocess.run(["git", "add", "."], cwd=task_b.worktree_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Resolve conflicts"], cwd=task_b.worktree_path, capture_output=True)

    # Now Task B can merge
    success, msg, _ = GitService.squash_merge(
        repo_path=str(repo_path),
        branch_name=task_b.branch_name,
        message="Merge Task B",
        target_branch=project.main_branch
    )
    assert success is True

    # Verify main has resolved content
    main_content = (repo_path / "shared.txt").read_text()
    assert main_content == "resolved content\n"
