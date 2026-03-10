"""
RepoCloner — clone or download a GitHub repository to a local temp directory.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import subprocess
import logging
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class RepoCloner:
    """Clone a remote Git repository into a temporary working directory."""

    def __init__(self, workspace_root: str | None = None):
        """
        Args:
            workspace_root: Base directory for cloned repos.
                            Defaults to a system temp directory.
        """
        self.workspace_root = workspace_root or os.path.join(
            tempfile.gettempdir(), "legacy_modernizer_repos"
        )
        os.makedirs(self.workspace_root, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def clone(self, repo_url: str, branch: str = "main") -> Path:
        """
        Clone *repo_url* and return the local path to the cloned directory.

        If the repo has already been cloned (same org/repo name), the old
        clone is removed and a fresh one is created.
        """
        repo_name = self._extract_repo_name(repo_url)
        dest = Path(self.workspace_root) / repo_name

        # Remove stale clone if present
        if dest.exists():
            logger.info("Removing existing clone at %s", dest)
            shutil.rmtree(dest)

        logger.info("Cloning %s (branch=%s) → %s", repo_url, branch, dest)

        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", "--branch", branch, repo_url, str(dest)],
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.CalledProcessError:
            # Branch might not exist — retry without explicit branch
            logger.warning("Branch '%s' not found, retrying with default branch.", branch)
            subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, str(dest)],
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )

        logger.info("Clone complete: %s", dest)
        return dest

    def cleanup(self, repo_path: Path) -> None:
        """Remove a previously cloned repository."""
        if repo_path.exists():
            shutil.rmtree(repo_path)
            logger.info("Cleaned up %s", repo_path)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_repo_name(repo_url: str) -> str:
        """Derive a filesystem-safe directory name from a GitHub URL."""
        parsed = urlparse(repo_url)
        path = parsed.path.rstrip("/")
        if path.endswith(".git"):
            path = path[:-4]
        # e.g. "/owner/repo" → "owner__repo"
        return path.strip("/").replace("/", "__")
