import fnmatch
import json
import pathlib

import aiida.orm
import aiida_shell

import aiida_benchcab.workflows
from aiida_benchcab.utils import load_singlefile_data

from .calculations import SVSCalculation
from .utils import SVS_DATA_DIR


@aiida.engine.calcfunction
def load_basin_input_files(remote_folder: aiida.orm.RemoteData):
    remote_path = pathlib.PurePosixPath(remote_folder.get_remote_path())
    return {
        file.replace(".csv", ""): aiida.orm.RemoteData(
            remote_path=str(remote_path / file),
            computer=remote_folder.computer,
        )
        for file in fnmatch.filter(remote_folder.listdir(), "basin_*.csv")
    }


@aiida.engine.calcfunction
def load_input_overrides_json(input_overrides_json: aiida.orm.SinglefileData):

    spec = SVSCalculation.spec()

    def _to_aiida_inputs(dict_obj, input_port):
        return {
            k: _to_aiida_inputs(v, port)
            if isinstance(port, aiida.engine.PortNamespace)
            else port.serialize(v)
            for k, v in dict_obj.items()
            if (port := input_port.get_port(k))
        }

    return _to_aiida_inputs(json.loads(input_overrides_json.get_content()), spec.inputs)


@aiida.engine.calcfunction
def load_svs_output_file(remote_folder: aiida.orm.RemoteData, file_name: aiida.orm.Str):
    remote_path = pathlib.PurePosixPath(remote_folder.get_remote_path())
    (file,) = fnmatch.filter(remote_folder.listdir(), file_name.value)
    return aiida.orm.RemoteData(
        remote_path=str(remote_path / file),
        computer=remote_folder.computer,
    )


class ShellJob(aiida_shell.ShellJob):
    @classmethod
    def define(cls, spec):
        super().define(spec)
        # The `ShellJob` class declares the `metadata.options.resources` input
        # as required when it isn't. This updates the required flag to reflect
        # the correct behaviour in the documentation:
        spec.inputs["metadata"]["options"]["resources"].required = False


class SVSFluxTowerWorkChain(aiida_benchcab.workflows.FluxTowerBaseWorkChain):
    """Flux tower workflow implementation for the SVS land surface model.

    For a given flux tower, this workflow first preprocesses the common flux
    tower meteorology into a format supported by MESH-SVS, followed by then
    running SVS1 or SVS2 using the preprocessed flux tower forcing, and lastly
    postprocessing the MESH-SVS output into NetCDF format for analysis.
    """

    model_name = "svs"

    # https://modelevaluation.org/model/display/znqi2kpAFHyCcqv2x
    model_profile_id = "znqi2kpAFHyCcqv2x"

    # TODO: Complete mapping of IGBP to SVS land cover types
    _n_svs_land_cover_types = 26
    _igbp_to_svs_land_cover = {
        "BSV": 25,
        "CRO": 25,
        "CSH": 25,
        "CVM": 25,
        "DBF": 25,
        "DNF": 25,
        "EBF": 25,
        "ENF": 25,
        "GRA": 25,
        "MF": 25,
        "OSH": 25,
        "SAV": 25,
        "SNO": 25,
        "URB": 25,
        "WAT": 25,
        "WET": 25,
        "WSA": 25,
    }

    _input_variable_to_basin_file = {
        "SWdown": "basin_shortwave.csv",
        "LWdown": "basin_longwave.csv",
        "Precip": "basin_rain.csv",
        "Tair": "basin_temperature.csv",
        "Qair": "basin_humidity.csv",
        "Wind": "basin_wind.csv",
        "Psurf": "basin_pres.csv",
    }

    _output_variable_names = {
        "QH": "Qh",
        "QE": "Qle",
    }

    _output_variable_attributes = {
        "Qh": {"units": "W/m2"},
        "Qle": {"units": "W/m2"},
    }

    @classmethod
    def define(cls, spec):
        super().define(spec)

        _shell_job_metadata_inputs = [
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
        ]

        spec.expose_inputs(
            ShellJob,
            include=_shell_job_metadata_inputs,
            namespace="preprocess_met",
            namespace_options={
                "help": (
                    "Options for pre-processing the common meteorological inputs "
                    "for use with SVS. This job requires an installation of "
                    "Python 3 with the ``xarray`` and ``netCDF4`` packages."
                ),
            },
        )
        spec.expose_inputs(
            SVSCalculation,
            exclude=[
                "code",  # inferred from `svs_code.code` input
                "mesh_parameters.schmsol",  # inferred from `lss` input
                "metadata.dry_run",  # this can only be set when running the calculation directly
                # The following inputs are inferred from the common flux tower
                # forcing data. See ``to_svs_inputs.py`` for more details.
                "basin_humidity",
                "basin_longwave",
                "basin_pres",
                "basin_rain",
                "basin_rain",
                "basin_shortwave",
                "basin_temperature",
                "basin_wind",
                "mesh_input_run_options.hourly_flag",
                "mesh_input_run_options.start_date",
                "mesh_parameters.deglat",
                "mesh_parameters.deglng",
                "mesh_parameters.zusl",
                "mesh_parameters.ztsl",
                "mesh_parameters.vf",
                "mesh_parameters.lout_half_hourly",
            ],
            namespace="svs_calculation",
            namespace_options={
                "help": "Inputs for ``SVSCalculation``.",
            },
        )
        spec.expose_inputs(
            ShellJob,
            include=_shell_job_metadata_inputs,
            namespace="postprocess_output",
            namespace_options={
                "help": (
                    "Options for postprocessing the SVS output files. This job "
                    "requires an installation of Python 3 with the ``xarray`` "
                    "and ``netCDF4`` packages."
                )
            },
        )
        spec.input_namespace(
            "svs_code",
            help="Options for setting the SVS code to use for the calculation.",
        )
        spec.input(
            "svs_code.code",
            valid_type=aiida.orm.Code,
            serializer=aiida.orm.load_code,
            help=(
                "The ``Code`` object (or its primary key, UUID or label) to use "
                "for the SVS calculation. To register a ``Code`` object from an "
                "installed executable, please see the ``verdi code create`` "
                "shell command."
            ),
        )
        spec.input(
            "lss",
            valid_type=aiida.orm.Str,
            serializer=aiida.orm.to_aiida_type,
            help=(
                "The land surface scheme to use for the SVS calculation. Must be "
                "one of `svs1` or `svs2`."
            ),
        )

        spec.outline(
            cls.preprocess_met_run,
            cls.preprocess_met_inspect,
            cls.calculation_run,
            cls.calculation_inspect,
            cls.postprocess_run,
            cls.postprocess_inspect,
        )

        spec.exit_code(
            400,
            "PRE_PROCESSING_ERROR",
            message="Failed to preprocess met input file: {message}",
        )
        spec.exit_code(
            500,
            "SVS_ERROR",
            message="SVS calculation failed: {message}",
        )
        spec.exit_code(
            600,
            "POST_PROCESSING_ERROR",
            message="Failed to postprocess SVS output files: {message}",
        )

    def preprocess_met_run(self):
        exposed_inputs = self.exposed_inputs(ShellJob, namespace="preprocess_met")

        metadata = exposed_inputs.metadata
        metadata.options.use_symlinks = True
        metadata.computer = self.inputs.base_inputs.computer

        _, node = aiida_shell.launch_shell_job(
            "python3",
            arguments="{script} {forcing_file}",
            nodes={
                "script": load_singlefile_data(
                    path=SVS_DATA_DIR / "scripts" / "to_svs_inputs.py",
                ),
                "forcing_file": self.inputs.base_inputs.site_forcing_file,
                "igbp_to_svs_land_cover_json": load_singlefile_data(
                    from_string=json.dumps(
                        {
                            "mapping": self._igbp_to_svs_land_cover,
                            "n_svs_land_cover_types": self._n_svs_land_cover_types,
                        }
                    ),
                ),
                "input_variable_to_basin_file_json": load_singlefile_data(
                    from_string=json.dumps(self._input_variable_to_basin_file),
                ),
            },
            filenames={
                "forcing_file": pathlib.PurePosixPath(
                    self.inputs.base_inputs.site_forcing_file.get_remote_path()
                ).name,
                "igbp_to_svs_land_cover_json": "igbp_to_svs_land_cover.json",
                "input_variable_to_basin_file_json": "input_variable_to_basin_file.json",
            },
            outputs=["input_overrides.json"],
            metadata=metadata,
            submit=True,
            resolve_command=False,
        )
        self.to_context(preprocess_met=node)

    def preprocess_met_inspect(self):
        result = self.ctx.preprocess_met
        if not result.is_finished_ok:
            return self.exit_codes.PRE_PROCESSING_ERROR.format(
                message="{}\nstdout='{}'\nstderr='{}'".format(
                    result.exit_message,
                    result.outputs.stdout.get_content().strip(),
                    result.outputs.stderr.get_content().strip()
                    if "stderr" in result.outputs
                    else "",
                )
            )

    def calculation_run(self):
        calc_builder = SVSCalculation.get_builder()
        calc_builder.code = self.inputs.svs_code.code
        calc_builder.mesh_parameters.schmsol = (
            "SVS" if self.inputs.lss.value == "svs1" else "SVS2"
        )
        for inputs in [
            self.exposed_inputs(SVSCalculation, namespace="svs_calculation"),
            load_basin_input_files(self.ctx.preprocess_met.outputs.remote_folder),
            load_input_overrides_json(
                self.ctx.preprocess_met.outputs.input_overrides_json
            ),
        ]:
            calc_builder._merge(inputs)
        self.to_context(calculation=self.submit(calc_builder))

    def calculation_inspect(self):
        result = self.ctx.calculation
        if not result.is_finished_ok:
            return self.exit_codes.SVS_ERROR.format(message=result.exit_message)

    def postprocess_run(self):
        exposed_inputs = self.exposed_inputs(ShellJob, namespace="postprocess_output")

        metadata = exposed_inputs.metadata
        metadata.computer = self.inputs.base_inputs.computer
        metadata.options.environment_variables = {
            **metadata.options.get("environment_variables", {}),
            "SVS_NC_OUT": self.inputs.base_inputs.output_filename.value,
            "SVS_LAT": str(self.ctx.calculation.inputs.mesh_parameters.deglat.value),
            "SVS_LON": str(self.ctx.calculation.inputs.mesh_parameters.deglng.value),
        }

        _, node = aiida_shell.launch_shell_job(
            "python3",
            arguments="{script} {lss}",
            nodes={
                "script": load_singlefile_data(
                    path=SVS_DATA_DIR / "scripts" / "generate_nc_output.py",
                ),
                "lss": self.inputs.lss,
                "output": self.ctx.calculation.outputs.output,
                "global_attributes_json": load_singlefile_data(
                    from_string=json.dumps(self.get_required_global_attributes())
                ),
                "output_variable_names": load_singlefile_data(
                    from_string=json.dumps(self._output_variable_names),
                ),
                "output_variable_attributes": load_singlefile_data(
                    from_string=json.dumps(self._output_variable_attributes),
                ),
            },
            filenames={
                "global_attributes_json": "global_attributes.json",
                "output_variable_attributes": "variable_attributes.json",
                "output_variable_names": "variable_names.json",
            },
            metadata=metadata,
            submit=True,
            resolve_command=False,
        )
        self.to_context(postprocess_run=node)

    def postprocess_inspect(self):
        result = self.ctx.postprocess_run
        if not result.is_finished_ok:
            return self.exit_codes.POST_PROCESSING_ERROR.format(
                message="{}\nstdout='{}'\nstderr='{}'".format(
                    result.exit_message,
                    result.outputs.stdout.get_content().strip(),
                    result.outputs.stderr.get_content().strip()
                    if "stderr" in result.outputs
                    else "",
                )
            )
        self.out(
            "base_outputs.output",
            load_svs_output_file(
                result.outputs.remote_folder,
                self.inputs.base_inputs.output_filename,
            ),
        )
