import pathlib
import tempfile

import aiida.common.exceptions
import aiida.common.log
import aiida.orm
import git

from aiida_benchcab.utils import get_installed_root

_logger = aiida.common.log.AIIDA_LOGGER.getChild(__name__)

_BUILD_CMD_TEMPLATE = """\
set -e
{prepend_text}
git -c init.defaultbranch=main init
git remote add origin {git_url}
git fetch --depth 1 origin {git_commit_hash}
git -c advice.detachedHead=false checkout FETCH_HEAD
bash build.bash
"""

CABLE_DATA_DIR = get_installed_root() / "models" / "cable" / "data"


def _git_ls_remote(url, patterns):
    remote_refs = []
    stdout = git.cmd.Git().ls_remote(url, *patterns)
    for line in stdout.split("\n"):
        commit, ref = line.split("\t")
        remote_refs.append((commit, ref))
    return remote_refs


def get_remote_filename(file: aiida.orm.RemoteData):
    return pathlib.PurePosixPath(file.get_remote_path()).name


def get_remote_content(file: aiida.orm.RemoteData):
    with (
        tempfile.NamedTemporaryFile() as tmp_file,
        file.computer.get_transport() as transport,
    ):
        transport.getfile(file.get_remote_path(), tmp_file.name)
        return pathlib.Path(tmp_file.name).read_text()


def build_code_from_source(
    computer,
    git_url,
    git_branch,
    git_commit_hash=None,
    extras=None,
    prepend_text="",
):

    if extras is None:
        extras = {}

    if not git_commit_hash:
        remote_refs = _git_ls_remote(git_url, [git_branch])
        if not remote_refs:
            raise ValueError(f"Branch {git_branch} not found in repository {git_url}")
        if len(remote_refs) > 1:
            raise ValueError(
                f"Multiple matching refs found for branch {git_branch} in repository {git_url}"
            )
        git_commit_hash, _ = remote_refs[0]

    code_label = f"cable-{git_branch}-{git_commit_hash[:7]}"
    _extras = {
        **extras,
        "git_url": git_url,
        "git_branch": git_branch,
        "git_commit_hash": git_commit_hash,
    }

    qb = aiida.orm.QueryBuilder()
    qb.append(
        aiida.orm.Computer,
        tag="computer",
        filters={"label": computer.label},
    ).append(
        aiida.orm.InstalledCode,
        with_computer="computer",
        filters={
            "label": code_label,
            **{f"extras.{k}": v for k, v in _extras.items()},
        },
    )

    if code := qb.first(flat=True):
        return code

    with computer.get_transport() as transport:
        _logger.report(
            f"Connected to computer Computer<{computer.label}>. Starting build process..."
        )
        return_code, stdout, stderr = transport.exec_command_wait("mktemp -d")
        if return_code != 0:
            raise RuntimeError(
                f"Failed to create temporary directory on computer Computer<{computer.label}>: {stdout=} {stderr=}"
            )
        dest_dir = pathlib.PurePosixPath(stdout.strip())
        _logger.report(f"Starting build in {dest_dir}")
        return_code, stdout, stderr = transport.exec_command_wait(
            _BUILD_CMD_TEMPLATE.format(
                git_url=git_url,
                git_commit_hash=git_commit_hash,
                prepend_text=prepend_text,
            ),
            workdir=dest_dir,
        )
        if return_code != 0:
            raise RuntimeError(
                f"Build failed with return code {return_code}: {stdout=} {stderr=}"
            )
        _logger.report(
            "Build completed successfully. Searching for executables in build directory..."
        )
        files = transport.listdir(dest_dir / "build", pattern="cable*")
        if not files:
            raise RuntimeError("No executables found in build directory")

    code = aiida.orm.InstalledCode(
        label=code_label,
        computer=computer,
        filepath_executable=str(dest_dir / "build" / files[0]),
    ).store()

    code.base.extras.set_many(_extras)

    _logger.report(
        f"Code<{code.label}> built successfully with pk<{code.pk}> on Computer<{computer.label}>"
    )

    return code
