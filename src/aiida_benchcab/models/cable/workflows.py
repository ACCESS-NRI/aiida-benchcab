import pathlib

import aiida.orm
import aiida_shell

import aiida_benchcab.workflows
from aiida_benchcab.utils import load_remote_data

from .calculations import CableCalculation
from .utils import (
    CABLE_DATA_DIR,
    build_code_from_source,
)


@aiida.engine.calcfunction
def return_example_output(computer_label: aiida.orm.Str) -> aiida.orm.RemoteData:
    return aiida.orm.RemoteData(
        computer=aiida.orm.load_computer(computer_label.value),
        remote_path=str(CABLE_DATA_DIR / "AU-Tum_cable_R0_S0_out.nc"),
    )


class ShellJob(aiida_shell.ShellJob):
    @classmethod
    def define(cls, spec):
        super().define(spec)
        # The `ShellJob` class declares the `metadata.options.resources` input
        # as required when it isn't. This updates the required flag to reflect
        # the correct behaviour in the documentation:
        spec.inputs["metadata"]["options"]["resources"].required = False


class CableFluxTowerWorkChain(aiida_benchcab.workflows.FluxTowerBaseWorkChain):
    """Flux tower workflow implementation for the CABLE land surface model.

    For a given flux tower, this workflow runs CABLE using the common flux tower
    forcing, and postprocesses the CABLE output suitable for analysis.
    """

    model_name = "cable"

    # https://modelevaluation.org/model/display/nFcjg4qqHGPkB9sqE
    model_profile_id = "nFcjg4qqHGPkB9sqE"

    _cable_default_repo_url = "https://github.com/CABLE-LSM/CABLE.git"

    @classmethod
    def define(cls, spec):
        super().define(spec)

        spec.expose_inputs(
            CableCalculation,
            exclude=[
                "cable_met_file",  # inferred from `base_inputs.site_forcing_file` input
                "cable_output_filename",  # inferred from `base_inputs.output_filename` input
                "code",  # inferred from `cable_code.code` input
                "metadata.dry_run",  # this can only be set when running the calculation directly
            ],
            namespace="cable_calculation",
            namespace_options={
                "help": "Inputs for ``CableCalculation``.",
            },
        )
        spec.expose_inputs(
            ShellJob,
            include=[
                "metadata.call_link_label",
                "metadata.description",
                "metadata.disable_cache",
                "metadata.label",
                "metadata.store_provenance",
                "metadata.options.account",
                "metadata.options.append_text",
                "metadata.options.custom_scheduler_commands",
                "metadata.options.environment_variables",
                "metadata.options.environment_variables_double_quotes",
                "metadata.options.import_sys_environment",
                "metadata.options.max_memory_kb",
                "metadata.options.max_wallclock_seconds",
                "metadata.options.prepend_text",
                "metadata.options.priority",
                "metadata.options.qos",
                "metadata.options.queue_name",
                "metadata.options.resources",
                "metadata.options.redirect_stderr",
            ],
            namespace="postprocess_output",
            namespace_options={
                "help": (
                    "Options for postprocessing the CABLE output file. This "
                    "job requires an installation of the netCDF Operator (NCO) "
                    "command line tools."
                ),
            },
        )

        spec.input_namespace(
            "cable_code",
            help=(
                "Options for setting the CABLE executable to use for the "
                "calculation. Either ``cable_code.code`` or ``cable_code.from_git`` "
                "options are required."
            ),
        )
        spec.input(
            "cable_code.code",
            valid_type=aiida.orm.Code,
            serializer=aiida.orm.load_code,
            required=False,
            help=(
                "The ``Code`` object (or its primary key, UUID or label) to use "
                "for the CABLE calculation. To register a ``Code`` object from an "
                "installed executable, please see the ``verdi code create`` "
                "shell command."
            ),
        )
        spec.input_namespace(
            "cable_code.from_git",
            required=False,
            help=(
                "Enabling these options will build the CABLE code on the remote "
                "computer from git source by invoking the build script in the "
                "CABLE repository, and will set ``cable_code.code`` to the built "
                "code. Any commands specified in the "
                "``cable_calculation.metadata.options.prepend_text`` input will "
                "be run before the build script is invoked."
            ),
        )
        spec.input(
            "cable_code.from_git.branch",
            valid_type=aiida.orm.Str,
            required=False,
            serializer=aiida.orm.to_aiida_type,
            non_db=True,
            help=(
                "The git branch to use for building the CABLE code on the remote "
                "computer."
            ),
        )
        spec.input(
            "cable_code.from_git.commit_hash",
            valid_type=aiida.orm.Str,
            required=False,
            serializer=aiida.orm.to_aiida_type,
            non_db=True,
            help=(
                "The git commit hash to use for building the CABLE code on the "
                "remote computer."
            ),
        )
        spec.input(
            "cable_code.from_git.url",
            valid_type=aiida.orm.Str,
            required=False,
            serializer=aiida.orm.to_aiida_type,
            non_db=True,
            help=(
                "The git URL to use for building the CABLE code on the remote computer."
            ),
        )
        for input, default_path in [
            ("cable_namelist", "src/offline/cable.nml"),
            ("cable_gridinfo_file", "src/offline/gridinfo_CSIRO_1x1.nc"),
            ("cable_pft_namelist", "src/offline/pft_params.nml"),
            ("cable_soil_namelist", "src/offline/cable_soilparm.nml"),
        ]:
            spec.input(
                "cable_calculation." + input + "_path",
                valid_type=str,
                non_db=True,
                default=default_path,
                help=(
                    f"The path of ``cable_calculation.{input}`` relative to the "
                    "root directory of the CABLE repository. Defaults to "
                    f"``{default_path}``."
                ),
            )
            spec.inputs["cable_calculation"][input].required = False
            spec.inputs["cable_calculation"][input].help += (
                " If ``cable_code.from_git`` options are used and this input is "
                "not provided, the default will be inferred from the CABLE source "
                f"repository using the ``cable_calculation.{input}_path`` input."
            )

        spec.input(
            "base_inputs.model_branch",
            valid_type=aiida.orm.Str,
            serializer=aiida.orm.to_aiida_type,
            help=(
                "The model branch/version name of the current simulation. If the "
                "CABLE code is built from git source, this will be set to the git "
                "branch (and commit hash if specified) used for the build."
            ),
        )

        spec.outline(
            cls.calculation_run,
            cls.calculation_inspect,
            cls.postprocess_run,
            cls.postprocess_inspect,
        )

        spec.exit_code(
            400, "CABLE_ERROR", message="CABLE calculation failed: {message}"
        )
        spec.exit_code(
            500,
            "POST_PROCESSING_ERROR",
            message="Failed to append attributes to output file: {message}",
        )

    @classmethod
    def configure_builder(cls, builder):

        if builder.cable_code.code:
            pass
        elif builder.cable_code.from_git.branch:
            extras = {}
            if builder.base_inputs.flux_tower_workchain_pk:
                extras["flux_tower_workchain_pk"] = (
                    builder.base_inputs.flux_tower_workchain_pk.value
                )
            try:
                prepend_text = builder["cable_calculation"]["metadata"]["options"][
                    "prepend_text"
                ]
            except KeyError:
                prepend_text = ""
            builder.cable_code.code = build_code_from_source(
                computer=builder.base_inputs.computer,
                git_branch=builder.cable_code.from_git.branch.value,
                git_commit_hash=builder.cable_code.from_git.commit_hash.value
                if builder.cable_code.from_git.commit_hash
                else None,
                git_url=builder.cable_code.from_git.url.value
                if builder.cable_code.from_git.url
                else cls._cable_default_repo_url,
                prepend_text=prepend_text,
                extras=extras,
            )
        else:
            raise RuntimeError(
                "Unable to determine CABLE code to use for calculation. See "
                "`cable_code` input namespace for options."
            )

        if branch := builder.cable_code.code.base.extras.get("git_branch", None):
            if commit_hash := builder.cable_code.code.base.extras.get(
                "git_commit_hash", None
            ):
                builder.base_inputs.model_branch = f"{branch}@{commit_hash[:7]}"
            else:
                builder.base_inputs.model_branch = branch
            for input in [
                "cable_namelist",
                "cable_gridinfo_file",
                "cable_pft_namelist",
                "cable_soil_namelist",
            ]:
                if input in builder.cable_calculation:
                    continue
                builder.cable_calculation[input] = load_remote_data(
                    remote_path=str(
                        builder.cable_code.code.filepath_executable.parent.parent
                        / getattr(builder.cable_calculation, input + "_path")
                    ),
                    computer=builder.cable_code.code.computer,
                    # The file is part of the repository and should not change,
                    # so no need to check the hash:
                    check_file_hash=False,
                )

    def calculation_run(self):
        inputs = {
            "cable_met_file": self.inputs.base_inputs.site_forcing_file,
            "cable_output_filename": self.inputs.base_inputs.output_filename.value,
            "code": self.inputs.cable_code.code,
            **self.exposed_inputs(CableCalculation, namespace="cable_calculation"),
        }
        self.to_context(calculation=self.submit(CableCalculation, **inputs))

    def calculation_inspect(self):
        result = self.ctx.calculation
        if not result.is_finished_ok:
            return self.exit_codes.CABLE_ERROR.format(message=result.exit_message)

    def postprocess_run(self):
        exposed_inputs = self.exposed_inputs(ShellJob, namespace="postprocess_output")

        metadata = exposed_inputs.metadata
        metadata.options.use_symlinks = True
        metadata.computer = self.inputs.base_inputs.computer

        _, node = aiida_shell.launch_shell_job(
            "ncatted",
            arguments=(
                " ".join(
                    f'-a "{key}",global,o,c,"{value}"'
                    for key, value in self.get_required_global_attributes().items()
                )
                + " {filename}"
            ),
            nodes={
                "filename": self.ctx.calculation.outputs.cable_output_file,
            },
            filenames={
                "filename": pathlib.PurePosixPath(
                    self.ctx.calculation.outputs.cable_output_file.get_remote_path()
                ).name
            },
            metadata=metadata,
            submit=True,
            resolve_command=False,
        )
        self.to_context(postprocess_run=node)

    def postprocess_inspect(self):
        if not self.ctx.postprocess_run.is_finished_ok:
            return self.exit_codes.POST_PROCESSING_ERROR.format(
                message="{}\nstdout='{}'\nstderr='{}'".format(
                    self.ctx.postprocess_run.exit_message,
                    self.ctx.postprocess_run.outputs.stdout.get_content().strip(),
                    self.ctx.postprocess_run.outputs.stderr.get_content().strip()
                    if "stderr" in self.ctx.postprocess_run.outputs
                    else "",
                )
            )
        self.out("base_outputs.output", self.ctx.calculation.outputs.cable_output_file)


class MockCableFluxTowerWorkChain(aiida_benchcab.workflows.FluxTowerBaseWorkChain):
    """Mock implementation of the CABLE flux tower workflow.

    This workflow is used for tutorial and testing purposes, and does not
    actually run CABLE. Instead, it returns a pre-computed output file for the
    AU-Tum experiment. This workflow can only be run on the computer where
    `aiida-benchcab` is installed.
    """

    model_name = CableFluxTowerWorkChain.model_name
    model_profile_id = CableFluxTowerWorkChain.model_profile_id

    @classmethod
    def define(cls, spec):
        super().define(spec)
        spec.input(
            "base_inputs.model_branch",
            valid_type=aiida.orm.Str,
            serializer=aiida.orm.to_aiida_type,
            default=lambda: aiida.orm.Str("mock"),
            help=(
                "The model branch name of the current simulation. This is "
                "set to 'mock' for the mock workflow."
            ),
        )
        spec.outline(cls.run_mock)

    def run_mock(self):
        if self.inputs.base_inputs.site_code != "AU-Tum":
            raise ValueError(
                "MockCableFluxTowerWorkChain only supports site_code 'AU-Tum'."
            )
        self.out(
            "base_outputs.output",
            return_example_output(self.inputs.base_inputs.computer.label),
        )
