import pathlib

import aiida.engine
import aiida.orm
import aiida_shell
import yaml

from aiida_benchcab.utils import get_installed_root, load_singlefile_data


@aiida.engine.calcfunction
def load_summary_file(summary_file: aiida.orm.SinglefileData) -> aiida.orm.Dict:
    return aiida.orm.Dict(yaml.safe_load(summary_file.get_content()))


class ShellJob(aiida_shell.ShellJob):
    @classmethod
    def define(cls, spec):
        super().define(spec)
        # The `ShellJob` class declares the `metadata.options.resources` input
        # as required when it isn't. This updates the required flag to reflect
        # the correct behaviour in the documentation:
        spec.inputs["metadata"]["options"]["resources"].required = False


class MeorgWorkChain(aiida.engine.WorkChain):
    """WorkChain for uploading model output files to modelevaluation.org via ``meorg_client``."""

    @classmethod
    def define(cls, spec):
        """Define the process specification."""
        super().define(spec)

        spec.expose_inputs(
            ShellJob,
            include=[
                "metadata.call_link_label",
                "metadata.computer",
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
            ],
            namespace="meorg",
            namespace_options={
                "help": "Configuration options for uploading simulation data to modelevaluation.org via the ``meorg_client`` command line tool.",
            },
        )
        spec.input_namespace(
            "meorg.model_output_files",
            valid_type=aiida.orm.RemoteData,
            dynamic=True,
            help="The model output files to upload to modelevaluation.org.",
        )
        spec.input(
            "meorg.output_name",
            valid_type=aiida.orm.Str,
            serializer=aiida.orm.to_aiida_type,
            help="The name of the model output on modelevaluation.org to upload the simulation data to.",
        )
        spec.input(
            "meorg.model_profile_id",
            valid_type=aiida.orm.Str,
            serializer=aiida.orm.to_aiida_type,
            help="The model profile ID on modelevaluation.org to associate the simulation data with.",
        )
        spec.input(
            "meorg.experiment_id",
            valid_type=aiida.orm.Str,
            serializer=aiida.orm.to_aiida_type,
            help="The modelevaluation.org experiment ID.",
        )
        spec.input(
            "meorg.benchmark_ids",
            valid_type=aiida.orm.List,
            serializer=aiida.orm.to_aiida_type,
            required=False,
            help="The model output IDs of the three machine learning based benchmarks to use for the PLUMBER2 analysis.",
        )
        spec.input(
            "meorg.force",
            valid_type=bool,
            default=False,
            non_db=True,
            help="Delete any existing model output files before uploading to modelevaluation.org.",
        )
        spec.input(
            "meorg.cache_delay",
            valid_type=int,
            default=10,
            non_db=True,
            help="Delay in seconds to wait for object store transfer to complete before running analysis.",
        )
        spec.input(
            "meorg.num_threads",
            valid_type=int,
            default=1,
            non_db=True,
            help="Number of parallel threads to use when uploading simulation data to modelevaluation.org.",
        )
        spec.input(
            "meorg.skip_upload",
            valid_type=bool,
            default=False,
            non_db=True,
            help="Skip the upload of simulation data to modelevaluation.org.",
        )
        spec.outline(
            cls.run_upload_script,
            cls.return_results,
        )

        spec.output("summary", valid_type=aiida.orm.Dict)

        spec.exit_code(
            400, "UPLOAD_SCRIPT_ERROR", message="Upload script error: {message}"
        )

    def run_upload_script(self):

        exposed_inputs = self.exposed_inputs(ShellJob, namespace="meorg")

        metadata = exposed_inputs.metadata
        metadata.options.use_symlinks = True
        metadata.options.redirect_stderr = True
        metadata.options.environment_variables = {
            **metadata.options.get("environment_variables", {}),
            "MEORG_UPLOAD_OUTPUT_NAME": self.inputs.meorg.output_name.value,
            "MEORG_UPLOAD_EXPERIMENT_ID": self.inputs.meorg.experiment_id.value,
            "MEORG_UPLOAD_MODEL_PROFILE_ID": self.inputs.meorg.model_profile_id.value,
            "MEORG_UPLOAD_BENCHMARK_IDS": ",".join(
                self.inputs.meorg.benchmark_ids.value
                if "benchmark_ids" in self.inputs.meorg
                else []
            ),
            "MEORG_UPLOAD_FORCE": "1" if self.inputs.meorg.force else "0",
            "MEORG_UPLOAD_CACHE_DELAY": self.inputs.meorg.cache_delay,
            "MEORG_UPLOAD_NUM_THREADS": self.inputs.meorg.num_threads,
            "MEORG_UPLOAD_DATA_DIR": ".",
            "MEORG_UPLOAD_SUMMARY_FILE": "summary.yaml",
        }

        _, node = aiida_shell.launch_shell_job(
            "bash",
            arguments="{script}",
            nodes={
                "script": load_singlefile_data(
                    path=get_installed_root() / "data" / "scripts" / "meorg_upload.sh",
                ),
                **self.inputs.meorg.model_output_files,
            },
            filenames={
                key: pathlib.PurePosixPath(f.get_remote_path()).name
                for key, f in self.inputs.meorg.model_output_files.items()
            },
            metadata=metadata,
            outputs=["summary.yaml"],
            submit=True,
            resolve_command=False,
        )
        self.to_context(upload_script=node)

    def return_results(self):
        result = self.ctx.upload_script
        if not result.is_finished_ok:
            message = result.exit_message
            stdout = result.outputs.stdout.get_content().strip()
            stderr = (
                result.outputs.stderr.get_content().strip()
                if "stderr" in result.outputs
                else ""
            )
            message += f"\nstdout='{stdout}'\nstderr='{stderr}'"
            if any("MEORG_UPLOAD_FORCE" in out for out in [stdout, stderr]):
                message += (
                    "\n\nThe upload script failed because the model output "
                    "already exists on modelevaluation.org. Please try rerunning "
                    "the workflow with either 'meorg.force=True' or changing the "
                    "'meorg.output_name' to be unique."
                )
            return self.exit_codes.UPLOAD_SCRIPT_ERROR.format(message=message)
        self.out("summary", load_summary_file(result.outputs.summary_yaml))
