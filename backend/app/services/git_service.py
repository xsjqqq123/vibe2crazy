import subprocess
import os
import logging
from pathlib import Path
from typing import Optional, List, TypedDict
import shutil
from app.config import settings
from app.services.file_service import MAX_FILE_SIZE, format_file_size

logger = logging.getLogger(__name__)


class FileStatusEntry(TypedDict):
    """TypedDict for file status entries returned by get_changed_files_with_status"""
    path: str
    status: str


class CommandExecution(TypedDict):
    """TypedDict for command execution details"""
    command: str
    exit_code: int
    stdout: str
    stderr: str
    working_dir: str


class GitService:
    """Service for Git operations including worktree management"""

    @staticmethod
    def _run_git_tracked(
        command: List[str],
        cwd: str,
        execution_log: Optional[List[CommandExecution]] = None
    ) -> subprocess.CompletedProcess:
        """
        Run a git command and optionally track it in the execution log.

        Args:
            command: List of command arguments
            cwd: Working directory
            execution_log: Optional list to append command execution details

        Returns:
            subprocess.CompletedProcess with the result
        """
        # Add -c core.quotePath=false to git commands that return filenames
        # to prevent octal quoting of non-ASCII characters
        if command[0] == "git" and ("status" in command or "diff" in command):
            command = ["git", "-c", "core.quotePath=false"] + command[1:]

        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, encoding='utf-8')

        # Record command execution if log is provided
        if execution_log is not None:
            cmd_str = " ".join(command)
            execution_log.append({
                "command": cmd_str,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "working_dir": cwd
            })

        return result

    @staticmethod
    def is_git_repository(path: str) -> bool:
        """Check if path is a valid git repository"""
        git_dir = Path(path) / ".git"
        is_valid = git_dir.exists() and git_dir.is_dir()
        logger.debug(f"Checking if {path} is git repo: {is_valid}")
        return is_valid

    @staticmethod
    def get_default_branch(path: str) -> str:
        """Get the default branch name of the repository"""
        logger.debug(f"Getting default branch for {path}")
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=path,
            capture_output=True,
            text=True, encoding="utf-8"
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            return branch if branch != "HEAD" else "main"
        return settings.git_default_branch

    @staticmethod
    def get_local_branches(path: str) -> tuple[list[str], str]:
        """
        Get all local branch names and current branch.

        Returns: (branches_list, current_branch)

        - Uses `git branch --no-color` to list all local branches
        - Parses output: current branch has '*' prefix, others are plain names
        - Returns sorted list of branch names and the current branch name
        """
        logger.debug(f"Getting local branches for {path}")
        try:
            result = subprocess.run(
                ["git", "branch", "--no-color"],
                cwd=path,
                capture_output=True,
                text=True, encoding="utf-8"
            )

            if result.returncode != 0:
                logger.error(f"Failed to get branches: {result.stderr}")
                return [], ""

            branches = []
            current_branch = ""

            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue

                # git branch output format:
                # "* main"  <- current branch (has * prefix)
                # "  develop" <- other branches (spaces prefix)
                line = line.strip()
                if line.startswith('*'):
                    # Current branch - remove * and leading/trailing spaces
                    current_branch = line[1:].strip()
                    branches.append(current_branch)
                else:
                    # Other branch
                    branch_name = line.strip()
                    if branch_name:
                        branches.append(branch_name)

            # Sort branches alphabetically
            branches = sorted(branches)

            logger.debug(f"Found {len(branches)} branches, current: {current_branch}")
            return branches, current_branch

        except Exception as e:
            logger.error(f"Error getting local branches: {e}")
            return [], ""

    @staticmethod
    def create_worktree(
        repo_path: str,
        branch_name: str,
        worktree_path: str,
        start_point: Optional[str] = None
    ) -> tuple[bool, str]:
        """
        Create a new git worktree
        Returns: (success, message)
        """
        logger.info(f"Creating git worktree: branch={branch_name}, path={worktree_path}")
        logger.debug(f"  Repo: {repo_path}")
        logger.debug(f"  Start point: {start_point}")

        try:
            # Create worktree directory parent if needed
            Path(worktree_path).parent.mkdir(parents=True, exist_ok=True)

            # Build command
            cmd = ["git", "worktree", "add", worktree_path, "-b", branch_name]
            if start_point:
                cmd.append(start_point)

            logger.debug(f"  Command: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True, encoding="utf-8"
            )

            if result.returncode == 0:
                logger.info(f"Worktree created successfully")

                # Configure git to not escape non-ASCII characters (for Chinese filename support)
                subprocess.run(
                    ["git", "config", "core.quotePath", "false"],
                    cwd=worktree_path,
                    capture_output=True,
                    text=True, encoding="utf-8"
                )

                return True, "Worktree created successfully"
            else:
                logger.error(f"Git worktree add failed: {result.stderr}")
                return False, result.stderr or result.stdout

        except Exception as e:
            logger.exception(f"Exception creating worktree: {e}")
            return False, str(e)

    @staticmethod
    def delete_worktree(worktree_path: str, repo_path: str) -> tuple[bool, str]:
        """
        Delete a git worktree
        Returns: (success, message)
        """
        logger.info(f"Deleting git worktree: {worktree_path}")
        try:
            result = subprocess.run(
                ["git", "worktree", "remove", worktree_path],
                cwd=repo_path,
                capture_output=True,
                text=True, encoding="utf-8"
            )

            if result.returncode == 0:
                logger.info(f"Worktree removed successfully via git")
                return True, "Worktree removed successfully"
            else:
                # Try manual removal if git command fails
                logger.warning(f"Git worktree remove failed, trying manual removal: {result.stderr}")
                if os.path.exists(worktree_path):
                    shutil.rmtree(worktree_path)
                logger.info(f"Worktree removed manually")
                return True, "Worktree removed manually"
        except Exception as e:
            logger.exception(f"Exception deleting worktree: {e}")
            return False, str(e)

    @staticmethod
    def get_changed_files(worktree_path: str, base_branch: str = "main") -> List[str]:
        """Get list of all uncommitted changes in worktree"""
        logger.debug(f"Getting changed files in {worktree_path}")
        try:
            all_files = set()

            # 1. Get unstaged changes (modified but not staged)
            # -c core.quotePath=false: output non-ASCII filenames without octal quoting
            result = subprocess.run(
                ["git", "-c", "core.quotePath=false", "diff", "--name-only"],
                cwd=worktree_path,
                capture_output=True,
                text=True, encoding="utf-8"
            )
            if result.returncode == 0:
                all_files.update(result.stdout.strip().split("\n"))

            # 2. Get staged changes
            result = subprocess.run(
                ["git", "-c", "core.quotePath=false", "diff", "--cached", "--name-only"],
                cwd=worktree_path,
                capture_output=True,
                text=True, encoding="utf-8"
            )
            if result.returncode == 0:
                all_files.update(result.stdout.strip().split("\n"))

            # 3. Get untracked files (new files not yet committed)
            # ls-files doesn't quote by default, but add core.quotePath=false for consistency
            result = subprocess.run(
                ["git", "-c", "core.quotePath=false", "ls-files", "--others", "--exclude-standard"],
                cwd=worktree_path,
                capture_output=True,
                text=True, encoding="utf-8"
            )
            if result.returncode == 0:
                all_files.update(result.stdout.strip().split("\n"))

            # Filter empty strings and sort
            files = sorted([f for f in all_files if f])
            logger.debug(f"Found {len(files)} changed/untracked files")
            return files
        except Exception as e:
            logger.error(f"Error getting changed files: {e}")
            return []

    @staticmethod
    def get_changed_files_with_status(worktree_path: str) -> List[FileStatusEntry]:
        """
        Get list of all uncommitted changes in worktree with Git status codes.
        Uses git status --porcelain for accurate status detection.

        Returns: List of FileStatusEntry dicts with 'path' and 'status' keys
        """
        logger.debug(f"Getting changed files with status in {worktree_path}")
        try:
            # Use git status --porcelain -uall to get status codes
            # Format: XY filename
            # X = staged status, Y = unstaged status
            # For new files: ?? filename
            # -uall: list all untracked files (not just directory names)
            # -c core.quotePath=false: output non-ASCII filenames without octal quoting
            result = subprocess.run(
                ["git", "-c", "core.quotePath=false", "status", "--porcelain", "-uall"],
                cwd=worktree_path,
                capture_output=True,
                text=True, encoding="utf-8"
            )

            if result.returncode != 0:
                logger.error(f"git status --porcelain failed: {result.stderr}")
                return []

            files = []
            for line in result.stdout.splitlines():
                if not line:
                    continue

                # Parse porcelain format: XY filename
                # X = staged status, Y = unstaged status (can be spaces)
                # XY are exactly TWO characters, then space, then filename
                if len(line) < 4:
                    continue  # Too short to be valid

                status_code = line[:2]  # First two characters are status codes
                filepath = line[3:]     # Skip two status chars + space to get filename

                # Git wraps filenames with special chars (spaces, quotes) in double quotes
                # Remove surrounding quotes if present
                if filepath.startswith('"') and filepath.endswith('"'):
                    filepath = filepath[1:-1]

                # Handle renamed files: R  old -> new
                if " -> " in filepath:
                    filepath = filepath.split(" -> ")[-1]

                # Skip directories - only show files in Changed Files
                full_path = Path(worktree_path) / filepath
                if full_path.is_dir():
                    continue

                # Map porcelain codes to single character
                # Priority: conflict status > unstaged status (Y) for working tree changes
                # Format: XY where X = staged, Y = unstaged (can be spaces)
                # Conflict codes: UU (both modified), AA (both added), AU/UA (added by us/them), DD (both deleted)
                if len(status_code) >= 2:
                    # Check for conflict status codes first
                    if status_code in ('UU', 'AA', 'AU', 'UA', 'DD'):
                        primary_status = 'U'  # Unmerged/conflict
                    # Prefer unstaged status (index 1) for working tree changes
                    elif status_code[1] != ' ':
                        primary_status = status_code[1]
                    elif status_code[0] != ' ':
                        primary_status = status_code[0]
                    else:
                        primary_status = "?"
                else:
                    primary_status = "?"

                files.append({
                    "path": filepath,
                    "status": primary_status
                })

            # Sort by path and filter empty
            files = sorted([f for f in files if f["path"]], key=lambda x: x["path"])
            logger.debug(f"Found {len(files)} changed files with status")
            return files

        except Exception as e:
            logger.error(f"Error getting changed files with status: {e}")
            return []

    @staticmethod
    def check_is_tracked(worktree_path: str, file_path: str) -> bool:
        """
        Check if a file is tracked by Git.
        Returns True if tracked, False if untracked.
        """
        try:
            result = subprocess.run(
                ["git", "ls-files", "--", file_path],
                cwd=worktree_path,
                capture_output=True,
                text=True, encoding="utf-8"
            )
            return bool(result.stdout.strip())
        except Exception:
            return False

    @staticmethod
    def revert_file(worktree_path: str, file_path: str) -> tuple[bool, str, bool]:
        """
        Revert a file to its last committed state.

        For tracked files: Uses git checkout -- <file>
        For untracked files: Deletes the file

        Returns: (success, message, is_tracked)
        """
        logger.info(f"Reverting {file_path} in {worktree_path}")

        # Check if file is tracked
        is_tracked = GitService.check_is_tracked(worktree_path, file_path)

        if is_tracked:
            # Use git checkout to restore file
            try:
                result = subprocess.run(
                    ["git", "checkout", "--", file_path],
                    cwd=worktree_path,
                    capture_output=True,
                    text=True, encoding="utf-8"
                )
                if result.returncode == 0:
                    logger.info(f"Successfully reverted tracked file: {file_path}")
                    return True, f"File reverted: {file_path}", True
                else:
                    error_msg = result.stderr.strip() or "Git checkout failed"
                    logger.error(f"Failed to revert {file_path}: {error_msg}")
                    return False, error_msg, True
            except Exception as e:
                logger.error(f"Exception reverting {file_path}: {e}")
                return False, str(e), True
        else:
            # Untracked file - use FileService to delete it
            from app.services.file_service import FileService
            success, error = FileService.delete_file(worktree_path, file_path)
            if success:
                logger.info(f"Deleted untracked file: {file_path}")
                return True, f"Deleted untracked file: {file_path}", False
            else:
                logger.error(f"Failed to delete untracked file {file_path}: {error}")
                return False, error or "Failed to delete file", False

    @staticmethod
    def stage_file(worktree_path: str, file_path: str) -> tuple[bool, str]:
        """
        Stage a file (git add) to mark conflicts as resolved.

        Returns: (success, message)
        """
        logger.info(f"Staging {file_path} in {worktree_path}")

        try:
            result = subprocess.run(
                ["git", "add", file_path],
                cwd=worktree_path,
                capture_output=True,
                text=True, encoding="utf-8"
            )
            if result.returncode == 0:
                logger.info(f"Successfully staged file: {file_path}")
                return True, f"File staged: {file_path}"
            else:
                error_msg = result.stderr.strip() or "Git add failed"
                logger.error(f"Failed to stage {file_path}: {error_msg}")
                return False, error_msg
        except Exception as e:
            logger.error(f"Exception staging {file_path}: {e}")
            return False, str(e)

    @staticmethod
    def get_file_diff(worktree_path: str, file_path: str, base_branch: str = "main") -> str:
        """Get diff for a specific file"""
        logger.debug(f"Getting diff for {file_path} in {worktree_path}")
        try:
            # First try to get diff against origin branch
            result = subprocess.run(
                ["git", "diff", f"origin/{base_branch}", "HEAD", "--", file_path],
                cwd=worktree_path,
                capture_output=True,
                text=True, encoding="utf-8"
            )

            # If origin doesn't exist, compare against the base branch directly
            if result.returncode != 0 or "unknown revision" in result.stderr:
                result = subprocess.run(
                    ["git", "diff", base_branch, "HEAD", "--", file_path],
                    cwd=worktree_path,
                    capture_output=True,
                    text=True, encoding="utf-8"
                )

            if result.returncode == 0:
                logger.debug(f"Diff generated, length: {len(result.stdout)} chars")
                return result.stdout
            return ""
        except Exception as e:
            logger.error(f"Error getting file diff: {e}")
            return ""

    @staticmethod
    def get_file_from_branch(repo_path: str, branch: str, file_path: str) -> str:
        """Get file content from a specific branch"""
        logger.debug(f"Getting {file_path} from {branch} in {repo_path}")
        try:
            result = subprocess.run(
                ["git", "show", f"{branch}:{file_path}"],
                cwd=repo_path,
                capture_output=True,
                text=True, encoding="utf-8"
            )

            if result.returncode == 0:
                logger.debug(f"File retrieved, length: {len(result.stdout)} chars")
                return result.stdout
            else:
                # File doesn't exist in base branch (new file)
                logger.debug(f"File doesn't exist in {branch}, returning empty content")
                return ""
        except Exception as e:
            logger.error(f"Error getting file from branch: {e}")
            return ""

    @staticmethod
    def get_file_from_worktree_head(worktree_path: str, file_path: str) -> str:
        """Get file content from HEAD commit in a worktree"""
        logger.debug(f"Getting {file_path} from HEAD in {worktree_path}")
        try:
            result = subprocess.run(
                ["git", "show", f"HEAD:{file_path}"],
                cwd=worktree_path,
                capture_output=True,
                text=True, encoding="utf-8"
            )

            if result.returncode == 0:
                logger.debug(f"File retrieved from worktree HEAD, length: {len(result.stdout)} chars")
                return result.stdout
            else:
                # File doesn't exist in HEAD (new file, not yet committed)
                logger.debug(f"File doesn't exist in worktree HEAD, returning empty content")
                return ""
        except Exception as e:
            logger.error(f"Error getting file from worktree HEAD: {e}")
            return ""

    @staticmethod
    def get_branch_status(worktree_path: str) -> dict:
        """Get current branch status information"""
        logger.debug(f"Getting branch status for {worktree_path}")
        try:
            # Get current branch
            branch_result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=worktree_path,
                capture_output=True,
                text=True, encoding="utf-8"
            )

            # Get commit count ahead
            ahead_result = subprocess.run(
                ["git", "rev-list", "--count", f"@{{u}}..HEAD"],
                cwd=worktree_path,
                capture_output=True,
                text=True, encoding="utf-8"
            )

            branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "unknown"
            ahead = int(ahead_result.stdout.strip()) if ahead_result.returncode == 0 else 0

            logger.debug(f"Branch status: branch={branch}, ahead={ahead}")
            return {
                "branch": branch,
                "commits_ahead": ahead
            }
        except Exception as e:
            logger.error(f"Error getting branch status: {e}")
            return {"branch": "unknown", "commits_ahead": 0}

    @staticmethod
    def get_latest_commit_hash(worktree_path: str) -> str | None:
        """Get the latest commit hash in worktree"""
        logger.debug(f"Getting latest commit hash for {worktree_path}")
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=worktree_path,
                capture_output=True,
                text=True, encoding="utf-8"
            )
            if result.returncode == 0:
                commit_hash = result.stdout.strip()
                logger.debug(f"Latest commit hash: {commit_hash}")
                return commit_hash
            return None
        except Exception as e:
            logger.error(f"Error getting latest commit hash: {e}")
            return None

    @staticmethod
    def _count_worktree_commits(worktree_path: str, main_branch: str = "main", direct_on_branch: bool = False) -> int:
        """Count total commits for a worktree.

        Args:
            worktree_path: Path to the git worktree
            main_branch: Name of the main branch
            direct_on_branch: If True, count recent commits on HEAD (no --no-merges)

        Returns:
            Number of commits (ahead of main for normal tasks, recent 100 for direct_on_branch)
        """
        try:
            # For direct_on_branch tasks, show recent commits (including merges)
            if direct_on_branch:
                cmd = [
                    "git", "-C", worktree_path,
                    "rev-list", "--count",
                    "HEAD", "-n", "100"
                ]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True, encoding="utf-8",
                    check=False
                )

                if result.returncode == 0:
                    count = int(result.stdout.strip())
                    logger.debug(f"Counted {count} recent commits (direct_on_branch)")
                    return count
                return 0

            # Normal mode: count commits ahead of main branch
            cmd = [
                "git", "-C", worktree_path,
                "rev-list", "--count", "--no-merges",
                f"{main_branch}..HEAD"
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True, encoding="utf-8",
                check=False
            )

            if result.returncode == 0:
                count = int(result.stdout.strip())
                logger.debug(f"Counted {count} commits ahead of {main_branch}")
                return count

            # Fallback: main branch reference doesn't exist, count all commits
            logger.warning(f"Main branch '{main_branch}' not found in worktree, counting all commits")
            cmd = [
                "git", "-C", worktree_path,
                "rev-list", "--count", "--no-merges",
                "HEAD"
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True, encoding="utf-8",
                check=False
            )

            if result.returncode == 0:
                count = int(result.stdout.strip())
                logger.debug(f"Counted {count} total commits (main branch not found)")
                return count

            return 0
        except (subprocess.CalledProcessError, ValueError, OSError) as e:
            logger.error(f"Error counting commits: {e}")
            return 0

    @staticmethod
    def _get_commit_files(worktree_path: str, commit_hash: str) -> List[dict]:
        """Get file changes for a specific commit.

        Args:
            worktree_path: Path to the git worktree
            commit_hash: Full commit hash

        Returns:
            List of file changes with path, status, additions, and deletions
        """
        try:
            # Get file changes using --stat
            stat_result = subprocess.run(
                ["git", "show", "--stat", "--format=", commit_hash],
                cwd=worktree_path,
                capture_output=True,
                text=True, encoding="utf-8",
                check=False
            )

            if stat_result.returncode != 0:
                return []

            files = []
            for stat_line in stat_result.stdout.strip().split('\n'):
                if not stat_line or '|' not in stat_line:
                    continue

                # Parse lines like: " path/to/file.py    | 12 +--"
                parts = stat_line.split('|')
                if len(parts) < 2:
                    continue

                file_path = parts[0].strip()
                if not file_path:
                    continue

                # Extract additions and deletions from the second part
                stats = parts[1]
                additions = stats.count('+')
                deletions = stats.count('-')

                # Determine file status
                status_result = subprocess.run(
                    ["git", "-c", "core.quotePath=false", "diff", "--name-status", f"{commit_hash}^..{commit_hash}"],
                    cwd=worktree_path,
                    capture_output=True,
                    text=True, encoding="utf-8",
                    check=False
                )

                status = 'M'  # Default to modified
                if status_result.returncode == 0:
                    for status_line in status_result.stdout.strip().split('\n'):
                        if status_line.startswith('A') and file_path in status_line:
                            status = 'A'
                            break
                        elif status_line.startswith('D') and file_path in status_line:
                            status = 'D'
                            break

                files.append({
                    'path': file_path,
                    'status': status,
                    'additions': additions,
                    'deletions': deletions
                })

            return files
        except Exception as e:
            logger.error(f"Error getting commit files: {e}")
            return []

    @staticmethod
    def _get_commits_page(worktree_path: str, main_branch: str, offset: int, limit: int, direct_on_branch: bool = False) -> List[dict]:
        """Get a page of commits from the worktree.

        Args:
            worktree_path: Path to the git worktree
            main_branch: Name of the main branch
            offset: Number of commits to skip
            limit: Maximum number of commits to return
            direct_on_branch: If True, get recent commits on HEAD (no --no-merges)

        Returns:
            List of commit dictionaries with hash, date, message, and files
        """
        # For direct_on_branch tasks, get recent commits (including merges)
        if direct_on_branch:
            cmd = [
                "git", "-C", worktree_path,
                "log",
                f"--skip={offset}", "-n", str(limit),
                "--format=%H|%ai|%s",
                "HEAD"
            ]
        else:
            # Normal mode: get commits ahead of main branch
            cmd = [
                "git", "-C", worktree_path,
                "log", "--no-merges",
                f"--skip={offset}", "-n", str(limit),
                "--format=%H|%ai|%s",
                f"{main_branch}..HEAD"
            ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True, encoding="utf-8",
            check=False
        )

        # Fallback: main branch reference doesn't exist, get all commits
        if result.returncode != 0 and not direct_on_branch:
            logger.warning(f"Main branch '{main_branch}' not found, listing all commits")
            cmd = [
                "git", "-C", worktree_path,
                "log", "--no-merges",
                f"--skip={offset}", "-n", str(limit),
                "--format=%H|%ai|%s",
                "HEAD"
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True, encoding="utf-8",
                check=False
            )

            if result.returncode != 0:
                logger.error(f"Failed to get commits: {result.stderr}")
                return []

        commits = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue

            hash_val, date_str, message = line.split('|', 2)

            commits.append({
                "hash": hash_val,
                "date": date_str,
                "message": message,
                "files": []
            })

        return commits

    @staticmethod
    def get_worktree_commits_paginated(
        worktree_path: str,
        main_branch: str = "main",
        offset: int = 0,
        limit: int = 30,
        direct_on_branch: bool = False
    ) -> dict:
        """Get paginated commits with metadata.

        Args:
            worktree_path: Path to the git worktree
            main_branch: Name of the main branch
            offset: Number of commits to skip (for pagination)
            limit: Maximum number of commits to return
            direct_on_branch: If True, show recent commits on HEAD instead of commits ahead of main

        Returns:
            Dictionary with items, total, page, page_size, total_pages
        """
        # Get total count
        total = GitService._count_worktree_commits(worktree_path, main_branch, direct_on_branch)

        # Calculate actual page and handle out of range
        if total == 0:
            return {
                "items": [],
                "total": 0,
                "page": 1,
                "page_size": limit,
                "total_pages": 0
            }

        # If offset is beyond total, return last page
        actual_offset = min(offset, total - 1)
        # Round down to nearest page boundary
        actual_offset = (actual_offset // limit) * limit

        # Get commits for current page
        items = GitService._get_commits_page(worktree_path, main_branch, actual_offset, limit, direct_on_branch)

        # Calculate pagination metadata
        page = (actual_offset // limit) + 1 if limit > 0 else 1
        total_pages = (total + limit - 1) // limit if limit > 0 else 0

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": limit,
            "total_pages": total_pages
        }

    @staticmethod
    def get_worktree_commits(worktree_path: str, main_branch: str = "main", limit: int = 20) -> List[dict]:
        """
        Get commits in worktree that are not yet merged to main branch.
        Returns: List of commits with hash, date, message, and changed files with line counts.
        """
        logger.debug(f"Getting worktree commits for {worktree_path} (not in {main_branch})")
        try:
            # Try to get commits ahead of upstream branch first
            ahead_range = f"@{{u}}..HEAD"
            result = subprocess.run(
                ["git", "log", ahead_range, "--format=%H|%ai|%s", "--no-merges", f"-{limit}"],
                cwd=worktree_path,
                capture_output=True,
                text=True, encoding="utf-8"
            )

            # If upstream doesn't exist, fall back to main branch comparison
            if result.returncode != 0 or not result.stdout.strip():
                result = subprocess.run(
                    ["git", "log", f"{main_branch}..HEAD", "--format=%H|%ai|%s", "--no-merges", f"-{limit}"],
                    cwd=worktree_path,
                    capture_output=True,
                    text=True, encoding="utf-8"
                )

            if result.returncode != 0:
                logger.error(f"Failed to get commits: {result.stderr}")
                return []

            lines = result.stdout.strip().split('\n')
            if not lines or lines == ['']:
                logger.debug("No commits found ahead of main branch")
                return []

            commits = []
            for line in lines:
                if not line or '|' not in line:
                    continue
                parts = line.split('|', 2)
                if len(parts) != 3:
                    continue

                full_hash, date_str, message = parts
                short_hash = full_hash[:8]

                # Get file changes for this commit using --stat
                stat_result = subprocess.run(
                    ["git", "show", "--stat", "--format=", full_hash],
                    cwd=worktree_path,
                    capture_output=True,
                    text=True, encoding="utf-8"
                )

                files = []
                if stat_result.returncode == 0:
                    # Parse the stat output to extract files with line counts
                    for stat_line in stat_result.stdout.strip().split('\n'):
                        if not stat_line or '|' not in stat_line:
                            continue

                        # Parse lines like: " path/to/file.py    | 12 +--"
                        # or " path/to/new.py | 5 ++++"
                        parts = stat_line.split('|')
                        if len(parts) < 2:
                            continue

                        file_path = parts[0].strip()
                        if not file_path:
                            continue

                        # Extract additions and deletions from the second part
                        stats = parts[1]
                        additions = 0
                        deletions = 0

                        # Count + and - symbols
                        additions = stats.count('+')
                        deletions = stats.count('-')

                        # Determine file status by checking if it exists in HEAD
                        status_result = subprocess.run(
                            ["git", "-c", "core.quotePath=false", "diff", "--name-status", f"{full_hash}^..{full_hash}"],
                            cwd=worktree_path,
                            capture_output=True,
                            text=True, encoding="utf-8"
                        )

                        status = 'M'  # Default to modified
                        if status_result.returncode == 0:
                            for status_line in status_result.stdout.strip().split('\n'):
                                if status_line.startswith('A') and file_path in status_line:
                                    status = 'A'
                                    break
                                elif status_line.startswith('D') and file_path in status_line:
                                    status = 'D'
                                    break

                        files.append({
                            'path': file_path,
                            'status': status,
                            'additions': additions,
                            'deletions': deletions
                        })

                commits.append({
                    'hash': full_hash,  # Full 40-character SHA-1
                    'date': date_str,
                    'message': message,
                    'files': files
                })

            logger.debug(f"Found {len(commits)} commits ahead of {main_branch}")
            return commits

        except Exception as e:
            logger.error(f"Error getting worktree commits: {e}")
            return []

    @staticmethod
    def auto_commit_worktree(worktree_path: str, message: str = "Auto-commit changes") -> tuple[bool, str]:
        """
        Automatically commit all changes in the worktree
        Returns: (success, message)
        """
        logger.info(f"Auto-committing changes in worktree: {worktree_path}")

        try:
            # Check if there are any changes
            status_result = subprocess.run(
                ["git", "-c", "core.quotePath=false", "status", "--porcelain"],
                cwd=worktree_path,
                capture_output=True,
                text=True, encoding="utf-8"
            )

            if status_result.returncode != 0:
                error_msg = f"Failed to check git status: {status_result.stderr}"
                logger.error(error_msg)
                return False, error_msg

            # If no changes, return success
            if not status_result.stdout.strip():
                logger.info("No changes to commit in worktree")
                return True, "No changes to commit"

            # Add all changes (including untracked files)
            logger.debug("Adding all changes to git")
            add_result = subprocess.run(
                ["git", "add", "-A"],
                cwd=worktree_path,
                capture_output=True,
                text=True, encoding="utf-8"
            )

            if add_result.returncode != 0:
                error_msg = f"Failed to add changes: {add_result.stderr}"
                logger.error(error_msg)
                return False, error_msg

            # Commit the changes
            logger.debug(f"Committing with message: {message}")
            commit_result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=worktree_path,
                capture_output=True,
                text=True, encoding="utf-8"
            )

            if commit_result.returncode != 0:
                # Check if nothing to commit (shouldn't happen after status check, but just in case)
                if "nothing to commit" in commit_result.stdout or "no changes" in commit_result.stdout:
                    logger.info("No changes to commit after add")
                    return True, "No changes to commit"
                error_msg = f"Failed to commit: {commit_result.stderr}"
                logger.error(error_msg)
                return False, error_msg

            # Get the commit hash (full hash for proper comparison in button states)
            hash_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=worktree_path,
                capture_output=True,
                text=True, encoding="utf-8"
            )

            # Use full hash to match get_latest_commit_hash() in button states logic
            full_hash = hash_result.stdout.strip() if hash_result.returncode == 0 else ""
            logger.info(f"Auto-committed changes: {full_hash}")
            return True, f"Committed changes ({full_hash})"

        except Exception as e:
            logger.exception(f"Exception during auto-commit: {e}")
            return False, str(e)

    @staticmethod
    def squash_merge(
        repo_path: str,
        branch_name: str,
        message: str,
        target_branch: str = "main",
        execution_log: Optional[List[CommandExecution]] = None
    ) -> tuple[bool, str, Optional[str]]:
        """
        Perform squash merge from branch to target branch
        Returns: (success, message, conflicts)
        """
        logger.info(f"Merging branch '{branch_name}' into '{target_branch}'")
        logger.debug(f"  Repo: {repo_path}")
        logger.debug(f"  Message: {message}")

        try:
            # Checkout target branch in main repo
            logger.debug(f"Checking out {target_branch}")
            checkout_result = GitService._run_git_tracked(
                ["git", "checkout", target_branch],
                repo_path,
                execution_log
            )

            if checkout_result.returncode != 0:
                error_msg = f"Failed to checkout target branch: {checkout_result.stderr}"
                logger.error(error_msg)
                return False, error_msg, None

            # Pull latest changes if origin exists
            logger.debug("Attempting to pull from origin")
            pull_result = GitService._run_git_tracked(
                ["git", "pull", "origin", target_branch],
                repo_path,
                execution_log
            )
            # Don't fail if pull fails (might not have origin)
            if pull_result.returncode == 0:
                logger.info(f"Pulled from origin/{target_branch}")
            else:
                logger.debug("No remote origin or pull failed (non-fatal)")

            # NEW: Two-phase merge for safety - test before committing
            logger.debug("Testing merge with --no-commit --no-ff")
            test_merge_result = GitService._run_git_tracked(
                ["git", "merge", "--no-commit", "--no-ff", branch_name],
                repo_path,
                execution_log
            )

            if test_merge_result.returncode != 0:
                # Test merge failed - rollback and report
                error_output = test_merge_result.stdout or test_merge_result.stderr or "Unknown merge error"
                logger.error(f"Test merge failed: {error_output}")
                GitService._run_git_tracked(["git", "merge", "--abort"], repo_path, None)
                GitService._run_git_tracked(["git", "reset", "--hard", "HEAD"], repo_path, None)
                return False, f"Merge test failed: {error_output}", None

            # Check for conflicts in test merge
            logger.debug("Checking test merge for conflicts")
            test_status = GitService._run_git_tracked(
                ["git", "status", "--porcelain"],
                repo_path,
                execution_log
            )

            if "UU" in test_status.stdout or "AA" in test_status.stdout:
                # Conflicts detected - rollback
                logger.warning("Conflicts detected in test merge, rolling back")
                GitService._run_git_tracked(["git", "merge", "--abort"], repo_path, None)
                GitService._run_git_tracked(["git", "reset", "--hard", "HEAD"], repo_path, None)
                return False, "Merge test failed: conflicts detected", None

            # Test succeeded - rollback the test merge and do real squash merge
            logger.debug("Test merge successful, rolling back test for squash merge")
            GitService._run_git_tracked(["git", "merge", "--abort"], repo_path, None)
            GitService._run_git_tracked(["git", "reset", "--hard", "HEAD"], repo_path, None)
            logger.info("Test merge passed, proceeding with squash merge")

            # Attempt squash merge
            logger.debug(f"Squash merging {branch_name}")
            merge_result = GitService._run_git_tracked(
                ["git", "merge", "--squash", branch_name],
                repo_path,
                execution_log
            )

            if merge_result.returncode != 0:
                # Git outputs error messages to stdout, not stderr
                error_output = merge_result.stdout or merge_result.stderr or "Unknown merge error"
                error_msg = f"Merge failed: {error_output}"
                logger.error(error_msg)
                return False, error_msg, None

            # Check for conflicts
            logger.debug("Checking for conflicts")
            status_result = GitService._run_git_tracked(
                ["git", "status", "--porcelain"],
                repo_path,
                execution_log
            )

            if "UU" in status_result.stdout or "AA" in status_result.stdout:
                logger.warning("Merge conflicts detected")
                return False, "Merge conflicts detected", status_result.stdout

            # Check if there's anything to commit after squash merge
            if not status_result.stdout.strip():
                logger.info("No changes to merge - branch is up to date")
                # Rollback the squash merge state
                GitService._run_git_tracked(["git", "reset", "--hard", "HEAD"], repo_path, None)
                return True, "No changes to merge", None

            # Commit the merge
            logger.debug("Committing merge")
            commit_result = GitService._run_git_tracked(
                ["git", "commit", "-m", message],
                repo_path,
                execution_log
            )

            if commit_result.returncode != 0:
                # Check if nothing to commit (already up to date)
                if "nothing to commit" in commit_result.stdout or "no changes" in commit_result.stdout:
                    logger.info("Already up to date - nothing to merge")
                    return True, "Already up to date", None
                error_msg = f"Failed to commit merge: {commit_result.stderr}"
                logger.error(error_msg)
                return False, error_msg, None

            logger.info(f"Merge successful: {branch_name} -> {target_branch}")
            return True, "Merge successful", None

        except Exception as e:
            logger.exception(f"Exception during merge: {e}")
            return False, str(e), None

    @staticmethod
    def delete_branch(repo_path: str, branch_name: str) -> tuple[bool, str]:
        """Delete a branch"""
        logger.info(f"Deleting branch: {branch_name}")
        try:
            result = subprocess.run(
                ["git", "branch", "-D", branch_name],
                cwd=repo_path,
                capture_output=True,
                text=True, encoding="utf-8"
            )

            if result.returncode == 0:
                logger.info(f"Branch deleted: {branch_name}")
                return True, "Branch deleted"
            logger.error(f"Failed to delete branch: {result.stderr}")
            return False, result.stderr or "Failed to delete branch"
        except Exception as e:
            logger.exception(f"Exception deleting branch: {e}")
            return False, str(e)

    @staticmethod
    def _get_conflicted_files(worktree_path: str) -> list[str]:
        """
        Get files that have merge conflicts according to git status.

        Args:
            worktree_path: Path to the git worktree

        Returns:
            List of filenames that have merge conflicts (UU, AA status)
        """
        status_result = subprocess.run(
            ["git", "-c", "core.quotePath=false", "status", "--porcelain"],
            cwd=worktree_path,
            capture_output=True,
            text=True, encoding="utf-8"
        )

        conflicted_files = []
        for line in status_result.stdout.strip().split('\n'):
            if not line:
                continue
            # Check for UU (both modified) or AA (both added)
            if line.startswith('UU') or line.startswith('AA'):
                parts = line.split()
                if len(parts) > 1:
                    conflicted_files.append(parts[1])

        return conflicted_files

    @staticmethod
    def sync_main_into_worktree(
        worktree_path: str,
        main_branch: str = "main",
        execution_log: Optional[List[CommandExecution]] = None
    ) -> tuple[bool, str, bool, list[str]]:
        """
        Sync main branch into worktree before final merge.
        Merges the local main branch directly into the worktree.

        Returns:
            (success, message, has_conflicts, conflicted_files)
        """
        logger.info(f"Syncing {main_branch} into worktree: {worktree_path}")

        try:
            # Merge local main branch into current worktree branch
            merge_target = main_branch
            logger.debug(f"Merging {merge_target} into worktree")
            merge_result = GitService._run_git_tracked(
                ["git", "merge", merge_target],
                worktree_path,
                execution_log
            )

            if merge_result.returncode != 0:
                # Check if it's just "already up to date" (support both English and Chinese)
                stdout_lower = merge_result.stdout.lower()
                if ("already up to date" in stdout_lower or
                    "already up-to-date" in stdout_lower or
                    "已经是最新" in merge_result.stdout or
                    "已经是最新的" in merge_result.stdout):
                    logger.info("Worktree already up to date with main")
                    return True, "Already up to date", False, []

                # Merge failed - check for conflicts
                logger.debug("Merge failed, checking for conflicts")
                conflicted_files = GitService._get_conflicted_files(worktree_path)

                if conflicted_files:
                    logger.warning(f"Merge conflicts detected: {conflicted_files}")
                    return False, "Merge conflicts detected", True, conflicted_files

                # Some other error
                error_msg = merge_result.stderr or merge_result.stdout
                logger.error(f"Merge failed with error: {error_msg}")
                return False, error_msg, False, []

            # Check for conflicts after successful merge command
            logger.debug("Checking git status for conflicts")
            conflicted_files = GitService._get_conflicted_files(worktree_path)

            if conflicted_files:
                # Merge command succeeded but left conflicts
                logger.warning(f"Merge completed with conflicts: {conflicted_files}")
                return False, "Merge conflicts detected", True, conflicted_files

            # No conflicts - merge is already committed by git
            logger.info("Sync successful: main merged into worktree")
            return True, "Sync successful", False, []

        except Exception as e:
            logger.exception(f"Exception during sync: {e}")
            return False, str(e), False, []

    @staticmethod
    def get_commit_diff(worktree_path: str, commit_hash: str, page: int = 1, page_size: int = 20) -> dict:
        """
        Get file changes for a specific commit (lightweight version without diff content).

        Returns dict with:
        - hash: commit hash (short)
        - date: commit date
        - message: commit message
        - files: list of file items (path, status, additions, deletions)
        - total_files: total number of files in commit
        - page: current page
        - page_size: items per page
        - total_pages: total number of pages
        """
        logger.debug(f"Getting commit diff for {commit_hash} in {worktree_path}, page={page}")
        try:
            # Get commit info (hash, date, message)
            commit_result = subprocess.run(
                ["git", "show", "--no-patch", "--format=%H|%ai|%s", commit_hash],
                cwd=worktree_path,
                capture_output=True,
                text=True, encoding="utf-8"
            )

            if commit_result.returncode != 0:
                logger.error(f"Failed to get commit info: {commit_result.stderr}")
                return {"files": [], "total_files": 0, "page": page, "page_size": page_size, "total_pages": 0}

            # Parse hash, date, message
            parts = commit_result.stdout.strip().split('|')
            if len(parts) < 3:
                logger.error(f"Invalid commit info format: {parts}")
                return {"files": [], "total_files": 0, "page": page, "page_size": page_size, "total_pages": 0}

            commit_hash_full = parts[0]
            commit_date = parts[1]
            commit_message = parts[2] if len(parts) > 2 else ""
            commit_hash_short = commit_hash_full[:8]

            # Get parent hash for diff
            parent_result = subprocess.run(
                ["git", "rev-parse", f"{commit_hash}^"],
                cwd=worktree_path,
                capture_output=True,
                text=True, encoding="utf-8"
            )

            parent_hash = parent_result.stdout.strip() if parent_result.returncode == 0 else None

            if not parent_hash:
                # Initial commit with no parent, return empty files
                return {
                    "hash": commit_hash_short,
                    "date": commit_date,
                    "message": commit_message,
                    "files": [],
                    "total_files": 0,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": 0
                }

            # Get all changed files in this commit with stats
            diff_result = subprocess.run(
                ["git", "-c", "core.quotePath=false", "diff", "--name-status", f"{parent_hash}..{commit_hash}"],
                cwd=worktree_path,
                capture_output=True,
                text=True, encoding="utf-8"
            )

            if diff_result.returncode != 0:
                logger.error(f"Failed to get commit diff: {diff_result.stderr}")
                return {"files": [], "total_files": 0, "page": page, "page_size": page_size, "total_pages": 0}

            # Also get stats for additions/deletions
            stats_result = subprocess.run(
                ["git", "diff", "--numstat", f"{parent_hash}..{commit_hash}"],
                cwd=worktree_path,
                capture_output=True,
                text=True, encoding="utf-8"
            )

            # Build a map of file -> (additions, deletions) from stats
            stats_map = {}
            if stats_result.returncode == 0:
                for line in stats_result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split('\t')
                        if len(parts) >= 3:
                            file_path = parts[2]
                            try:
                                additions = int(parts[0]) if parts[0] != '-' else 0
                                deletions = int(parts[1]) if parts[1] != '-' else 0
                                stats_map[file_path] = (additions, deletions)
                            except ValueError:
                                stats_map[file_path] = (0, 0)

            # Parse git diff output to get file changes
            files_list = []
            lines = diff_result.stdout.strip().split('\n')

            for line in lines:
                if not line:
                    continue

                # Parse diff name-status lines (format: "STATUS<TAB>filename" or "STATUS<metadata>TAB>filename")
                if '\t' in line and line[0] in ['M', 'A', 'D', 'R', 'C']:
                    parts = line.split('\t')
                    status_part = parts[0]
                    status_char = status_part[0]
                    file_path = parts[-1].strip()

                    # Only handle M, A, D
                    if status_char not in ['M', 'A', 'D']:
                        continue

                    # Get stats
                    stats = stats_map.get(file_path, (0, 0))
                    additions, deletions = stats

                    files_list.append({
                        'path': file_path,
                        'status': status_char,
                        'additions': additions,
                        'deletions': deletions
                    })

            total_files = len(files_list)
            total_pages = (total_files + page_size - 1) // page_size if total_files > 0 else 0

            # Paginate
            start = (page - 1) * page_size
            end = start + page_size
            paginated_files = files_list[start:end]

            logger.debug(f"Found {total_files} files in commit {commit_hash}, returning page {page}/{total_pages}")
            return {
                "hash": commit_hash_short,
                "date": commit_date,
                "message": commit_message,
                "files": paginated_files,
                "total_files": total_files,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages
            }

        except Exception as e:
            logger.error(f"Error getting commit diff: {e}")
            return {"files": [], "total_files": 0, "page": page, "page_size": page_size, "total_pages": 0}

    @staticmethod
    def get_file_diff(worktree_path: str, commit_hash: str, file_path: str) -> dict:
        """
        Get diff content for a single file in a commit.

        Args:
            worktree_path: Path to the git worktree
            commit_hash: Commit hash
            file_path: Path to the file

        Returns dict with:
            - path: file path
            - status: 'A', 'M', or 'D'
            - original: original content (empty string for added files)
            - modified: modified content (empty string for deleted files)
        """
        logger.debug(f"Getting file diff for {file_path} in commit {commit_hash}")
        try:
            # Get parent hash
            parent_result = subprocess.run(
                ["git", "rev-parse", f"{commit_hash}^"],
                cwd=worktree_path,
                capture_output=True,
                text=True, encoding="utf-8"
            )

            parent_hash = parent_result.stdout.strip() if parent_result.returncode == 0 else None

            # Get file status in this commit
            status_result = subprocess.run(
                ["git", "diff", "--name-status", f"{parent_hash or commit_hash}..{commit_hash}"],
                cwd=worktree_path,
                capture_output=True,
                text=True, encoding="utf-8"
            )

            status_char = 'M'
            if status_result.returncode == 0:
                for line in status_result.stdout.strip().split('\n'):
                    if '\t' in line and line.split('\t')[-1].strip() == file_path:
                        status_char = line[0]
                        break

            # Handle based on status
            if status_char == 'D':
                # Deleted file: show original content only
                try:
                    original_result = subprocess.run(
                        ["git", "show", f"{parent_hash}:{file_path}"],
                        cwd=worktree_path,
                        capture_output=True,
                        text=True, encoding="utf-8",
                        errors='replace'
                    )
                    original_content = original_result.stdout if original_result.returncode == 0 else ''
                except Exception:
                    original_content = ''

                return {
                    'path': file_path,
                    'status': 'D',
                    'original': original_content,
                    'modified': ''
                }
            else:
                # Added or Modified file
                # Check file size first
                size_result = subprocess.run(
                    ["git", "cat-file", "-s", f"{commit_hash}:{file_path}"],
                    cwd=worktree_path,
                    capture_output=True,
                    text=True, encoding="utf-8"
                )

                if size_result.returncode == 0:
                    try:
                        file_size = int(size_result.stdout.strip())
                        if file_size > MAX_FILE_SIZE:
                            size_formatted = format_file_size(file_size)
                            return {
                                'path': file_path,
                                'status': 'A' if status_char == 'A' else 'M',
                                'original': '',
                                'modified': f'[File too large to display ({size_formatted})]'
                            }
                    except ValueError:
                        pass

                # Get original content (empty for new files)
                original_content = ''
                if parent_hash:
                    try:
                        original_result = subprocess.run(
                            ["git", "show", f"{parent_hash}:{file_path}"],
                            cwd=worktree_path,
                            capture_output=True,
                            text=True, encoding="utf-8",
                            errors='replace'
                        )
                        original_content = original_result.stdout if original_result.returncode == 0 else ''
                    except Exception:
                        original_content = ''

                # Get modified content
                try:
                    modified_result = subprocess.run(
                        ["git", "show", f"{commit_hash}:{file_path}"],
                        cwd=worktree_path,
                        capture_output=True,
                        text=True, encoding="utf-8",
                        errors='replace'
                    )
                    modified_content = modified_result.stdout if modified_result.returncode == 0 else ''
                except Exception:
                    modified_content = ''

                return {
                    'path': file_path,
                    'status': 'A' if status_char == 'A' else 'M',
                    'original': original_content,
                    'modified': modified_content
                }

        except Exception as e:
            logger.error(f"Error getting file diff: {e}")
            return {'path': file_path, 'status': 'M', 'original': '', 'modified': ''}

    @staticmethod
    def reset_to_commit(worktree_path: str, commit_hash: str, include_commit: bool = False) -> tuple[bool, str]:
        """Reset working directory to specified commit (git reset --mixed).

        Args:
            worktree_path: Path to the git worktree
            commit_hash: Hash of the commit to reset to
            include_commit: If True, reset to parent of commit_hash (include selected commit in undo)

        Returns:
            Tuple of (success, message)
        """
        logger.info(f"Resetting worktree {worktree_path} to commit {commit_hash[:8]}, include_commit={include_commit}")
        try:
            # Determine the target commit for reset
            target_hash = commit_hash
            if include_commit:
                # Check if commit has a parent (not root commit)
                parent_check = subprocess.run(
                    ["git", "-C", worktree_path, "rev-parse", f"{commit_hash}^"],
                    capture_output=True, text=True, encoding="utf-8", check=False
                )
                if parent_check.returncode != 0:
                    return False, "Cannot include the first commit"
                target_hash = parent_check.stdout.strip()
                logger.info(f"Reset target: parent of {commit_hash[:8]} = {target_hash[:8]}")

            cmd = [
                "git", "-C", worktree_path,
                "reset", "--mixed", target_hash
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True, encoding="utf-8",
                check=False
            )

            if result.returncode == 0:
                logger.info(f"Successfully reset to commit {target_hash[:8]}")
                return True, f"Reset to commit {target_hash[:8]}"
            else:
                error_msg = result.stderr or "Unknown error"
                logger.error(f"Failed to reset to commit {target_hash[:8]}: {error_msg}")
                return False, error_msg
        except Exception as e:
            logger.error(f"Exception resetting to commit: {e}")
            return False, str(e)

