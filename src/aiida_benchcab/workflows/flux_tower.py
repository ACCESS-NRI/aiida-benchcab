import abc
import copy
import fnmatch
import pathlib
import string

import aiida.engine
import aiida.orm
import aiida.plugins
from aiida.engine import if_

import aiida_benchcab.workflows
from aiida_benchcab.utils import deep_update, load_remote_data


class FluxTowerBaseWorkChain(aiida.engine.WorkChain, abc.ABC):
    """Base workflow for running a land surface model at a flux tower.

    This class must be subclassed by model-specific implementations to be run as
    part of the flux tower workflow.
    """

    _required_attributes = [
        ("model_name", str),
        ("model_profile_id", str),
    ]

    __doc__ += (
        " In addition to the standard AiiDA constructs, implementations of this "
        "workflow must define class attributes: "
        + ", ".join(f"'{attr_name}'" for attr_name, _ in _required_attributes)
        + "."
    )

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for attr_name, attr_type in cls._required_attributes:
            if not hasattr(cls, attr_name) or not isinstance(
                getattr(cls, attr_name), attr_type
            ):
                raise TypeError(
                    f"Class '{cls.__name__}' must define required attribute "
                    f"'{attr_name}' of type '{attr_type.__name__}'"
                )

    def get_required_global_attributes(self):
        """Return a dictionary of required global attributes for the model output file.

        Note: Global attributes such as `cable_branch` and `filename%out` are
        left over from the original benchcab tool used only for CABLE. This
        should be renamed in the future.
        """
        return {
            "cable_branch": self.inputs.base_inputs.model_branch.value,
            r"filename%out": self.inputs.base_inputs.output_filename.value,
            "benchcab_version": f"aiida-benchcab v{aiida_benchcab.__version__}",
        }

    @classmethod
    def configure_builder(cls, builder):
        """Configure the input builder for this model specific workflow.

        This class method is called in `FluxTowerWorkChain.flux_tower_init` to
        allow for model specific configuration of the input builder. This class
        method is called for each configured model simulation in serial (after
        the inputs have been merged with the default, realisation and science
        configuration inputs).
        """

    @classmethod
    def define(cls, spec):
        """Define the process specification."""
        super().define(spec)

        spec.input_namespace(
            "base_inputs",
            help=(
                "The following inputs are available to all model "
                "implementations. It can be assumed that all non-required inputs "
                "will be provided by the flux tower workflow and that all "
                "required inputs will be either specified directly by the user "
                "or by the model workflow implementation."
            ),
        )
        spec.input(
            "base_inputs.workflow_plugin",
            valid_type=str,
            non_db=True,
            required=False,
            help=(
                "The entry point name of a model workflow to run. This is set by "
                "the ``model_inputs.workflow_plugin`` input of "
                "``FluxTowerWorkChain``."
            ),
        )
        spec.input(
            "base_inputs.model_branch",
            valid_type=aiida.orm.Str,
            serializer=aiida.orm.to_aiida_type,
            help="The model branch/version name of the current simulation.",
        )
        spec.input(
            "base_inputs.computer",
            valid_type=aiida.orm.Computer,
            non_db=True,
            required=False,
            help=(
                "The computer (local or remote) on which to run the model "
                "simulation. This is set by the ``computer`` input of "
                "``FluxTowerWorkChain``."
            ),
        )
        spec.input(
            "base_inputs.flux_tower_workchain_pk",
            valid_type=aiida.orm.Int,
            serializer=aiida.orm.to_aiida_type,
            required=False,
            help=(
                "The primary key of the current ``FluxTowerWorkChain`` run. This is "
                "set by the ``FluxTowerWorkChain``."
            ),
        )
        spec.input(
            "base_inputs.site_code",
            valid_type=aiida.orm.Str,
            serializer=aiida.orm.to_aiida_type,
            required=False,
            help=(
                "The flux tower site code for the simulation. This is set "
                "according to the ``experiment`` input of "
                "``FluxTowerWorkChain``."
            ),
        )
        spec.input(
            "base_inputs.site_forcing_file",
            valid_type=aiida.orm.RemoteData,
            required=False,
            help=(
                "The flux tower site forcing file for the simulation. This is "
                "set according to the ``experiment`` input of "
                "``FluxTowerWorkChain``."
            ),
        )
        spec.input(
            "base_inputs.task_label",
            valid_type=aiida.orm.Str,
            serializer=aiida.orm.to_aiida_type,
            required=False,
            help=(
                "The label for the simulation. This is set by the ``task_label`` "
                "input of ``FluxTowerWorkChain``."
            ),
        )
        spec.input(
            "base_inputs.output_filename",
            valid_type=aiida.orm.Str,
            serializer=aiida.orm.to_aiida_type,
            required=False,
            help=(
                "The name of the model output file. This is set using the "
                "``task_label`` input of ``FluxTowerWorkChain``."
            ),
        )

        spec.output_namespace(
            "base_outputs",
            help=(
                "Common outputs for all model implementations of the base flux "
                "tower workflow."
            ),
        )
        spec.output(
            "base_outputs.output",
            valid_type=aiida.orm.RemoteData,
            help=(
                "The output file produced by the model run. The output file "
                "must: 1. be in netCDF format; 2. have a time coordinate variable "
                "with units in seconds and of double precision type; 3. define "
                "required global attributes (see "
                "``FluxTowerBaseWorkChain.get_required_global_attributes``); "
                "and 4. define the ``units`` variable attribute."
            ),
        )


class FluxTowerWorkChain(aiida.engine.WorkChain):
    """Implementation of the benchcab flux tower evaluation workflow."""

    _default_task_label = "{site_code}_{model_name}_{realisation_id}_{configuration_id}"

    _BENCHCAB_EXPERIMENTS = {
        "AU-Tum": {
            "site_codes": ["AU-Tum"],
            "experiment_id": "jwN9jNMWLEzbT2i9D",
            "experiment_name": "AU-Tum-P2",
            "benchmark_ids": [
                "J9BBQCJdsuehsmMf2",
                "N5X2rjmp96baXrrJ3",
                "Q7Xu6yGGYdzvvAwbn",
            ],
        },
        "AU-How": {
            "site_codes": ["AU-How"],
            "experiment_id": "XfC6MTEMm23C4m4iL",
            "experiment_name": "AU-How-P2",
            "benchmark_ids": [
                "tdrQrKmaihmWdZSZu",
                "qZWhR3g7JfGhKWPa7",
                "p2SFiZdQw6ChQK6pr",
            ],
        },
        "FI-Hyy": {
            "site_codes": ["FI-Hyy"],
            "experiment_id": "nXpDC2Yt7RhhwSKor",
            "experiment_name": "FI-Hyy-P2",
            "benchmark_ids": [
                "Ym7gwY4k2J2pvDKDJ",
                "xYA3tSrL2bCeEmvai",
                "kXFt8mCMtHG4rsnJz",
            ],
        },
        "US-Var": {
            "site_codes": ["US-Var"],
            "experiment_id": "sD9N2dKx4Jca8B82T",
            "experiment_name": "US-Var-P2",
            "benchmark_ids": [
                "NbMEBX4sPNHNYkTtq",
                "X3FoGtYvWmjCyRHGd",
                "uejBLuHnf4RxAqZXH",
            ],
        },
        "US-Whs": {
            "site_codes": ["US-Whs"],
            "experiment_id": "aWDKqBoTe88ssinuc",
            "experiment_name": "US-Whs-P2",
            "benchmark_ids": [
                "QWsdgXGCWYx7HobXJ",
                "C42GurGaYDdSRrc2x",
                "zdnCDJXJzuSheP6T5",
            ],
        },
        "five-site-test": {
            "site_codes": ["AU-Tum", "AU-How", "FI-Hyy", "US-Var", "US-Whs"],
            "experiment_id": "Nb37QxkAz3FczWDd7",
            "experiment_name": "Five site test",
            "benchmark_ids": [
                "PP4rFWJGiixFZP8q4",
                "8kWgyuSkwAKyghsFp",
                "DYWQuYvxZDgEsp4iX",
            ],
        },
        "forty-two-site-test": {
            "site_codes": [
                "AU-Tum",
                "AU-How",
                "AU-Cum",
                "AU-ASM",
                "AU-GWW",
                "AU-Ctr",
                "AU-Stp",
                "BR-Sa3",
                "CA-Qfo",
                "CH-Dav",
                "CN-Cha",
                "CN-Din",
                "DE-Geb",
                "DE-Gri",
                "DE-Hai",
                "DE-Tha",
                "DK-Sor",
                "FI-Hyy",
                "FR-Gri",
                "FR-Pue",
                "GF-Guy",
                "IT-Lav",
                "IT-MBo",
                "IT-Noe",
                "NL-Loo",
                "RU-Fyo",
                "US-Blo",
                "US-GLE",
                "US-Ha1",
                "US-Me2",
                "US-MMS",
                "US-Myb",
                "US-NR1",
                "US-PFa",
                "US-FPe",
                "US-SRM",
                "US-SRG",
                "US-Ton",
                "US-UMB",
                "US-Var",
                "US-Whs",
                "US-Wkg",
            ],
            "experiment_id": "s6k22L3WajmiS9uGv",
            "experiment_name": "Forty two site test",
            "benchmark_ids": [
                "zKRrfM7bJpxWPcQ3L",
                "LMvzc2WL5Qa5jKTpv",
                "D3XqYwQgH88Tx6NCW",
            ],
        },
    }

    @classmethod
    def define(cls, spec):
        super().define(spec)

        spec.expose_inputs(
            aiida_benchcab.workflows.MeorgWorkChain,
            exclude=[
                "meorg.model_output_files",
                "meorg.model_profile_id",
                "meorg.experiment_id",
                "meorg.benchmark_ids",
                "meorg.metadata.computer",
            ],
        )
        spec.input(
            "site_meteorology_path",
            valid_type=aiida.orm.RemoteData,
            help=(
                "Path on remote computer to the directory containing site meteorology "
                "files for the *{}* experiment on modelevaluation.org "
                "(experiment ID: ``{}``)".format(
                    cls._BENCHCAB_EXPERIMENTS["forty-two-site-test"]["experiment_name"],
                    cls._BENCHCAB_EXPERIMENTS["forty-two-site-test"]["experiment_id"],
                )
            ),
        )
        spec.input(
            "computer",
            valid_type=aiida.orm.Computer,
            serializer=aiida.orm.load_computer,
            non_db=True,
            help="The primary key, UUID or label of a computer (local or remote) on which to run the workflow.",
        )
        spec.input(
            "task_label",
            valid_type=aiida.orm.Str,
            required=False,
            serializer=aiida.orm.to_aiida_type,
            help=(
                "Label for naming each model run task. The label should be a "
                "format string with the following keys: {}. Default: ``{}``.".format(
                    ", ".join(
                        f"``{k}``"
                        for _, k, _, _ in string.Formatter().parse(
                            cls._default_task_label
                        )
                    ),
                    cls._default_task_label,
                )
            ),
        )
        spec.input(
            "experiment",
            valid_type=aiida.orm.Str,
            serializer=aiida.orm.to_aiida_type,
            help=(
                "The benchcab experiment type on modelevaluation.org. Must be one of "
                "the following: {}.".format(
                    ", ".join(
                        f"``{k}`` (ID: ``{v['experiment_id']}``)"
                        for k, v in cls._BENCHCAB_EXPERIMENTS.items()
                    ),
                )
            ),
        )
        spec.input_namespace(
            "model_inputs",
            help=(
                "This namespace allows for specifying the various model "
                "configurations to compare and test against in the final "
                "analysis. Each configuration specified in this namespace must "
                "satisfy the input specification corresponding to "
                "``model_inputs.workflow_plugin``. When used, the "
                "``model_inputs.realisations`` and "
                "``model_inputs.science_configurations`` namespace options are "
                "applied on top of those specified in the "
                "``model_inputs.defaults`` namespace, with the "
                "``model_inputs.realisations`` namespace being applied first, "
                "followed by the ``model_inputs.science_configurations`` "
                "namespace.  Multiple specifications in the "
                "``model_inputs.realisations`` and "
                "``model_inputs.science_configurations`` namespaces allow for "
                "generating a matrix of model configurations which each "
                "corresponding to a unique model simulation. The "
                "``model_inputs.realisations`` and "
                "``model_inputs.science_configurations`` namespaces are optional "
                "and if not specified will contain a single 'empty' "
                "configuration."
            ),
        )
        spec.input(
            "model_inputs.workflow_plugin",
            valid_type=str,
            non_db=True,
            help=(
                "The entry point name of the model workflow to run. Valid entry points are:\n {}".format(
                    ", ".join(
                        sorted(
                            f"``{name}``"
                            for name in aiida.plugins.get_entry_points(
                                "aiida.workflows"
                            ).names
                            if name.startswith("benchcab.flux_tower.")
                        )
                    )
                )
            ),
        )
        spec.input_namespace(
            "model_inputs.defaults",
            dynamic=True,
            help=(
                "Default inputs for the model workflow corresponding to "
                "``model_inputs.workflow_plugin`` to use for all model simulations. These "
                "inputs may be overwritten by inputs specified in the "
                "``model_inputs.realisations`` and ``model_inputs.science_configurations`` namespaces."
            ),
        )
        spec.input_namespace(
            "model_inputs.realisations",
            dynamic=True,
            required=False,
            help=(
                "Realisation-specific inputs for the model workflow "
                "corresponding to ``model_inputs.workflow_plugin``. These inputs will "
                "overwrite inputs specified in the ``model_inputs.defaults`` "
                "namespace. If not specified, this namespace will contain a "
                "single 'empty' configuration. Inputs specified in the "
                "``model_inputs.science_configurations`` namespace may overwrite inputs "
                "specified in this namespace. Each key-value pair in this "
                "namespace must be specified as ``R<number>: {<inputs>}`` where "
                "``<inputs>`` is a dictionary of inputs for the model specific "
                "workflow."
            ),
        )
        spec.input_namespace(
            "model_inputs.science_configurations",
            dynamic=True,
            required=False,
            help=(
                "Configuration-specific inputs for the model workflow "
                "corresponding to ``model_inputs.workflow_plugin``. These inputs will "
                "overwrite inputs specified in the ``model_inputs.defaults`` and "
                "``model_inputs.realisations`` namespaces. If not specified, this "
                "namespace will contain a single 'empty' configuration. Each "
                "key-value pair in this namespace must be specified as "
                "``S<number>: {<inputs>}`` where ``<inputs>`` is a dictionary of "
                "inputs for the model specific workflow."
            ),
        )

        spec.output_namespace(
            "results", dynamic=True, help="Results of each model simulation."
        )
        spec.output(
            "meorg_upload_summary",
            valid_type=aiida.orm.Dict,
            required=False,
            help="Summary of the uploaded analysis on modelevaluation.org.",
        )

        spec.outline(
            cls.flux_tower_init,
            cls.flux_tower_tasks_run,
            cls.flux_tower_tasks_inspect,
            if_(cls.flux_tower_meorg_upload)(
                cls.flux_tower_meorg_upload_run,
                cls.flux_tower_meorg_upload_inspect,
            ),
        )

        spec.exit_code(500, "INIT_FAILURE", message="Initialisation failure: {message}")
        spec.exit_code(
            600, "RUN_FAILURE", message="One or more model runs have failed."
        )
        spec.exit_code(
            700,
            "MEORG_UPLOAD_FAILURE",
            message="Upload to modelevaluation.org failed: {message}",
        )

    def flux_tower_init(self):
        self.report("Setting up workflow...")

        self.ctx.task_label = self.inputs.get(
            "task_label", aiida.orm.Str(self._default_task_label)
        )
        self.ctx.workflow_builders = []

        self.ctx.site_inputs = []
        site_meteorology_path = pathlib.PurePosixPath(
            self.inputs.site_meteorology_path.get_remote_path()
        )
        files = self.inputs.site_meteorology_path.listdir()
        for site_code in self._BENCHCAB_EXPERIMENTS[self.inputs.experiment.value][
            "site_codes"
        ]:
            try:
                (unique_file,) = fnmatch.filter(files, f"*{site_code}*")
            except ValueError as e:
                return self.exit_codes.INIT_FAILURE.format(
                    message=(
                        f"Could not find a unique forcing file for site "
                        f"{site_code} in {site_meteorology_path}: {e}"
                    )
                )
            self.ctx.site_inputs.append(
                (
                    site_code,
                    load_remote_data(
                        remote_path=str(site_meteorology_path / unique_file),
                        computer=self.inputs.computer,
                    ),
                )
            )

        process_class = aiida.plugins.WorkflowFactory(
            self.inputs.model_inputs.workflow_plugin
        )
        if not issubclass(process_class, FluxTowerBaseWorkChain):
            raise TypeError(
                f"Workflow plugin {self.inputs.model_inputs.workflow_plugin} does "
                "not implement the required interface for flux tower "
                "workflows."
            )

        self.ctx.default_inputs = self.inputs.model_inputs.get("defaults", {})
        self.ctx.realisations = self.inputs.model_inputs.get("realisations", {"R0": {}})
        self.ctx.science_configurations = self.inputs.model_inputs.get(
            "science_configurations", {"S0": {}}
        )
        for site_code, site_forcing_file in self.ctx.site_inputs:
            for realisation_id, realisation_spec in self.ctx.realisations.items():
                for (
                    configuration_id,
                    configuration_spec,
                ) in self.ctx.science_configurations.items():
                    inputs = copy.deepcopy(
                        deep_update(
                            {},
                            self.ctx.default_inputs,
                            realisation_spec,
                            configuration_spec,
                        )
                    )
                    task_label = self.ctx.task_label.value.format(
                        site_code=site_code,
                        model_name=process_class.model_name,
                        realisation_id=realisation_id,
                        configuration_id=configuration_id,
                    )
                    inputs["base_inputs"] = {
                        **inputs.get("base_inputs", {}),
                        "workflow_plugin": self.inputs.model_inputs.workflow_plugin,
                        "site_code": site_code,
                        "site_forcing_file": site_forcing_file,
                        "task_label": task_label,
                        "output_filename": task_label + "_out.nc",
                        "computer": self.inputs.computer,
                        "flux_tower_workchain_pk": self.node.pk,
                    }
                    builder = process_class.get_builder()
                    builder._merge(inputs)
                    process_class.configure_builder(builder)
                    self.ctx.workflow_builders.append(builder)

        self.report(
            f"tasks: {len(self.ctx.workflow_builders)} (sites: "
            f"{len(self.ctx.site_inputs)}, realisations: "
            f"{len(self.ctx.realisations)}, science_configurations: "
            f"{len(self.ctx.science_configurations)})"
        )

    def flux_tower_tasks_run(self):
        for builder in self.ctx.workflow_builders:
            node = self.submit(builder)
            self.report(
                f"Submitting task: {builder.base_inputs.task_label.value} (pk: "
                f"{node.pk})"
            )
            self.to_context(results=aiida.engine.append_(node))

    def flux_tower_tasks_inspect(self):
        success = []
        failed = []
        for i, result in enumerate(self.ctx.results):
            if not result.is_finished_ok:
                self.report(
                    f"{result.inputs.base_inputs.task_label.value} "
                    f"(pk: {result.pk}) "
                    f"failed: {result.exit_message}"
                )
                failed.append((i, result))
            else:
                success.append((i, result))

        self.report(f"{len(failed)} failed, {len(success)} passed")

        if failed:
            return self.exit_codes.RUN_FAILURE

        results = {}
        for i, result in enumerate(self.ctx.results):
            results.update(
                {
                    str(i): {
                        "model_name": result.process_class.model_name,
                        "site_code": result.inputs.base_inputs.site_code.value,
                        **result.outputs.base_outputs,
                    }
                }
            )
        self.out("results", results)

    def flux_tower_meorg_upload(self):
        inputs = self.exposed_inputs(aiida_benchcab.workflows.MeorgWorkChain)
        if inputs.meorg.skip_upload:
            self.report("Skipping upload to modelevaluation.org")
        return not inputs.meorg.skip_upload

    def flux_tower_meorg_upload_run(self):
        self.report("Uploading results to modelevaluation.org...")
        inputs = self.exposed_inputs(aiida_benchcab.workflows.MeorgWorkChain)
        inputs.meorg.model_output_files = {
            str(i): result.outputs.base_outputs.output
            for i, result in enumerate(self.ctx.results)
        }
        inputs.meorg.metadata.computer = self.inputs.computer
        inputs.meorg.experiment_id = self._BENCHCAB_EXPERIMENTS[
            self.inputs.experiment.value
        ]["experiment_id"]
        inputs.meorg.benchmark_ids = self._BENCHCAB_EXPERIMENTS[
            self.inputs.experiment.value
        ]["benchmark_ids"]
        process_class = aiida.plugins.WorkflowFactory(
            self.inputs.model_inputs.workflow_plugin
        )
        inputs.meorg.model_profile_id = process_class.model_profile_id
        self.to_context(
            meorg_upload=self.submit(aiida_benchcab.workflows.MeorgWorkChain, **inputs)
        )

    def flux_tower_meorg_upload_inspect(self):
        if not self.ctx.meorg_upload.is_finished_ok:
            return self.exit_codes.MEORG_UPLOAD_FAILURE.format(
                message=self.ctx.meorg_upload.exit_message,
            )
        self.report("Upload complete. Results have been uploaded to:")
        self.report(
            self.ctx.meorg_upload.outputs.summary.get_dict()["model_output_url"]
        )
        self.out("meorg_upload_summary", self.ctx.meorg_upload.outputs.summary)
