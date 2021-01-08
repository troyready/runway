"""'Git type Path Source."""
import logging
import os
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional

from .source import Source

LOGGER = logging.getLogger(__name__)


class Git(Source):
    """Git Path Source.

    The Git path source can be tasked with cloning a remote repository
    and pointing to a specific module folder (or the root).

    """

    def __init__(self, uri="", location="", options=None, **kwargs):
        # type: (str, str, Optional[Dict[str, str]], Any) -> None
        """Git Path Source.

        Keyword Args:
            uri (str): The uniform resource identifier that targets the remote git
                repository
            location (str): The relative location to the root of the
                repository where the module resides. Leaving this as an empty
                string, ``/``, or ``./`` will have runway look in the root folder.
            options (Optional[Dict[str, str]]): A reference can be passed along via the
                options so that a specific version of the repository is cloned.
                **commit**, **tag**, **branch**  are all valid keys with
                respective output

        """
        self.uri = uri
        self.location = location
        self.options = options

        if not self.options:
            self.options = {}

        super().__init__(**kwargs)

    def fetch(self):
        # type: () -> str
        """Retrieve the git repository from it's remote location."""
        from git import Repo  # pylint: disable=import-outside-toplevel

        ref = self.__determine_git_ref()  # type: str
        dir_name = "_".join([self.sanitize_git_path(self.uri), ref])  # type: str
        cached_dir_path = os.path.join(self.cache_dir, dir_name)  # type: str
        cached_path = ""  # type: str

        if not os.path.isdir(cached_dir_path):
            tmp_dir = tempfile.mkdtemp()
            try:
                tmp_repo_path = os.path.join(tmp_dir, dir_name)  # type: str
                with Repo.clone_from(self.uri, tmp_repo_path) as repo:
                    repo.head.reference = ref  # type: str
                    repo.head.reset(index=True, working_tree=True)
                shutil.move(tmp_repo_path, self.cache_dir)
                cached_path = os.path.join(self.cache_dir, dir_name)  # type: str
            finally:
                shutil.rmtree(tmp_dir)
        else:
            cached_path = cached_dir_path  # type: str

        return os.path.join(cached_path, self.location)

    def __git_ls_remote(self, ref):
        # type: (str) -> str
        """List remote repositories based on uri and ref received.

        Keyword Args:
            ref (str): The git reference value

        """
        cmd = ["git", "ls-remote", self.uri, ref]
        LOGGER.debug("getting commit ID from repo: %s", " ".join(cmd))
        lsremote_output = subprocess.check_output(cmd)
        # pylint: disable=unsupported-membership-test
        if b"\t" in lsremote_output:
            commit_id = lsremote_output.split(b"\t")[0]  # type List[str]
            LOGGER.debug("matching commit id found: %s", commit_id)
            return commit_id
        raise ValueError('Ref "%s" not found for repo %s.' % (ref, self.uri))

    def __determine_git_ls_remote_ref(self):
        # type: () -> str
        """Determine remote ref, defaulting to HEAD unless a branch is found."""
        ref = "HEAD"

        if self.options.get("branch"):
            ref = "refs/heads/%s" % self.options.get("branch")  # type: str

        return ref

    def __determine_git_ref(self):
        # type: () -> str
        """Determine the git reference code."""
        ref_config_keys = 0  # type: int

        for i in ["commit", "tag", "branch"]:
            if self.options.get(i):
                ref_config_keys += 1
        if ref_config_keys > 1:
            raise ImportError(
                "Fetching remote git sources failed: conflicting revisions "
                "(e.g. 'commit', 'tag', 'branch') specified for a package source"
            )

        if self.options.get("commit"):
            ref = self.options.get("commit")  # type: str
        elif self.options.get("tag"):
            ref = self.options.get("tag")  # type: str
        else:
            ref = self.__git_ls_remote(
                self.__determine_git_ls_remote_ref()
            )  # ty pe: str
        if isinstance(ref, bytes):
            return ref.decode()
        return ref

    @classmethod
    def sanitize_git_path(cls, path):
        # type(str) -> str
        """Sanitize the git path for folder/file assignment.

        Keyword Args:
            path (str): The path string to be sanitized

        """
        dir_name = path  # type: str
        split = path.split("//")  # type: List[str]
        domain = split[len(split) - 1]  # type: str

        if domain.endswith(".git"):
            dir_name = domain[:-4]

        return cls.sanitize_directory_path(dir_name)
