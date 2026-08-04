import string

import aiida
import aiida.orm

from aiida_benchcab.models.svs.utils import SVS_DATA_DIR


class SVSCalculation(aiida.engine.CalcJob):
    """Calculation plugin for running the MESH-SVS code.

    For more information, see:
    https://mesh-model.atlassian.net/wiki/spaces/USER/pages/6390037/Soil-Vegetation-Snow+SVS
    """

    @classmethod
    def define(cls, spec):
        super().define(spec)

        spec.input(
            "metadata.options.resources",
            valid_type=dict,
            default={"num_machines": 1, "num_mpiprocs_per_machine": 1},
        )
        spec.input(
            "metadata.options.withmpi",
            valid_type=bool,
            default=False,
            help="Set the calculation to use mpi.",
        )
        spec.input(
            "metadata.options.parser_name",
            valid_type=str,
            default="benchcab.models.svs_parser",
            help="Set the parser name for the calculation.",
        )
        spec.input(
            "basin_humidity",
            valid_type=aiida.orm.RemoteData,
            help="Basin humidity CSV file.",
        )
        spec.input(
            "basin_longwave",
            valid_type=aiida.orm.RemoteData,
            help="Basin long wave CSV file.",
        )
        spec.input(
            "basin_pres",
            valid_type=aiida.orm.RemoteData,
            help="Basin pressure CSV file.",
        )
        spec.input(
            "basin_rain",
            valid_type=aiida.orm.RemoteData,
            help="Basin precipitation CSV file.",
        )
        spec.input(
            "basin_shortwave",
            valid_type=aiida.orm.RemoteData,
            help="Basin short wave CSV file.",
        )
        spec.input(
            "basin_temperature",
            valid_type=aiida.orm.RemoteData,
            help="Basin temperature CSV file.",
        )
        spec.input(
            "basin_wind",
            valid_type=aiida.orm.RemoteData,
            help="Basin wind speed CSV file.",
        )
        spec.input_namespace(
            "mesh_input_soil_levels",
            help="Inputs for generating the MESH_input_soil_levels.txt file.",
        )
        spec.input(
            "mesh_input_soil_levels.delz",
            valid_type=aiida.orm.List,
            serializer=aiida.orm.to_aiida_type,
            help=(
                "List of soil layer thicknesses in meters. Corresponds to the first "
                "column of MESH_input_soil_levels.txt."
            ),
        )
        spec.input(
            "mesh_input_soil_levels.dl_svs",
            valid_type=aiida.orm.List,
            serializer=aiida.orm.to_aiida_type,
            help=(
                "List of total depths for each soil layer in meters. Corresponds "
                "to the second column of MESH_input_soil_levels.txt."
            ),
        )
        spec.input_namespace(
            "mesh_input_run_options",
            help="Inputs for interpolating the MESH_input_run_options.ini.in template file.",
        )
        spec.input_namespace(
            "mesh_parameters",
            help=("Inputs for interpolating the MESH_parameters.txt.in template file."),
        )
        for input_spec in [
            {
                "name": "mesh_parameters.deglat",
                "valid_type": aiida.orm.Float,
                "serializer": aiida.orm.to_aiida_type,
                "help": "Latitude of the site in degrees.",
            },
            {
                "name": "mesh_parameters.deglng",
                "valid_type": aiida.orm.Float,
                "serializer": aiida.orm.to_aiida_type,
                "help": "Longitude of the site in degrees.",
            },
            {
                "name": "mesh_parameters.vf",
                "valid_type": aiida.orm.List,
                "serializer": aiida.orm.to_aiida_type,
                "help": "List of fractions for each SVS land cover type.",
            },
            {
                "name": "mesh_parameters.ztsl",
                "valid_type": aiida.orm.Float,
                "serializer": aiida.orm.to_aiida_type,
                "help": "Reference height of forcing data for momentum.",
            },
            {
                "name": "mesh_parameters.zusl",
                "valid_type": aiida.orm.Float,
                "serializer": aiida.orm.to_aiida_type,
                "help": "Reference height of forcing data for temperature and humidity.",
            },
            {
                "name": "mesh_parameters.slop",
                "valid_type": aiida.orm.Float,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Float(0.0),
            },
            {
                "name": "mesh_parameters.draindens",
                "valid_type": aiida.orm.Float,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Float(0.0),
            },
            {
                "name": "mesh_parameters.schmsol",
                "valid_type": aiida.orm.Str,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Str("SVS2"),
            },
            {
                "name": "mesh_parameters.lwater_ponding_svs",
                "valid_type": aiida.orm.Bool,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Bool(False),
            },
            {
                "name": "mesh_parameters.watpond",
                "valid_type": aiida.orm.Float,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Float(0.0),
            },
            {
                "name": "mesh_parameters.lmacropores_svs",
                "valid_type": aiida.orm.Bool,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Bool(False),
            },
            {
                "name": "mesh_parameters.soiltext",
                "valid_type": aiida.orm.Str,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Str("NIL"),
            },
            {
                "name": "mesh_parameters.sand",
                "valid_type": aiida.orm.List,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.List([60.0, 60.0, 60.0]),
            },
            {
                "name": "mesh_parameters.clay",
                "valid_type": aiida.orm.List,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.List([30.0, 30.0, 30.0]),
            },
            {
                "name": "mesh_parameters.wsoil",
                "valid_type": aiida.orm.List,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.List([0.083, 0.086, 0.098]),
            },
            {
                "name": "mesh_parameters.isoil",
                "valid_type": aiida.orm.List,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.List([0.0, 0.0, 0.0]),
            },
            {
                "name": "mesh_parameters.tpsoil",
                "valid_type": aiida.orm.List,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.List([280.0, 280.0, 280.0]),
            },
            {
                "name": "mesh_parameters.lbcheat_svs2",
                "valid_type": aiida.orm.Str,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Str("TPERM"),
            },
            {
                "name": "mesh_parameters.tperm",
                "valid_type": aiida.orm.Float,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Float(280.0),
            },
            {
                "name": "mesh_parameters.tvegeh",
                "valid_type": aiida.orm.Float,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Float(285.7),
            },
            {
                "name": "mesh_parameters.wveg_vh",
                "valid_type": aiida.orm.Float,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Float(0.0),
            },
            {
                "name": "mesh_parameters.tvegel",
                "valid_type": aiida.orm.Float,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Float(285.7),
            },
            {
                "name": "mesh_parameters.wveg_vl",
                "valid_type": aiida.orm.Float,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Float(0.0),
            },
            {
                "name": "mesh_parameters.tgroundv",
                "valid_type": aiida.orm.Float,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Float(284.8),
            },
            {
                "name": "mesh_parameters.tground",
                "valid_type": aiida.orm.Float,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Float(284.8),
            },
            {
                "name": "mesh_parameters.nsl",
                "valid_type": aiida.orm.Int,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Int(20),
            },
            {
                "name": "mesh_parameters.hsnowscheme",
                "valid_type": aiida.orm.Str,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Str("CRO"),
            },
            {
                "name": "mesh_parameters.hsnowdrift_cro",
                "valid_type": aiida.orm.Str,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Str("VI13"),
            },
            {
                "name": "mesh_parameters.lsnowdrift_sublim",
                "valid_type": aiida.orm.Bool,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Bool(False),
            },
            {
                "name": "mesh_parameters.hsnowmetamo",
                "valid_type": aiida.orm.Str,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Str("B21"),
            },
            {
                "name": "mesh_parameters.hsnowrad",
                "valid_type": aiida.orm.Str,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Str("B92"),
            },
            {
                "name": "mesh_parameters.hsnowfall",
                "valid_type": aiida.orm.Str,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Str("V12"),
            },
            {
                "name": "mesh_parameters.hsnowcond",
                "valid_type": aiida.orm.Str,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Str("Y81"),
            },
            {
                "name": "mesh_parameters.hsnowhold",
                "valid_type": aiida.orm.Str,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Str("B92"),
            },
            {
                "name": "mesh_parameters.hsnowcomp",
                "valid_type": aiida.orm.Str,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Str("B92"),
            },
            {
                "name": "mesh_parameters.hsnowres",
                "valid_type": aiida.orm.Str,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Str("RIL"),
            },
            {
                "name": "mesh_parameters.lsnowaging_var",
                "valid_type": aiida.orm.Bool,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Bool(False),
            },
            {
                "name": "mesh_parameters.agingcoef",
                "valid_type": aiida.orm.Float,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Float(60.0),
            },
            {
                "name": "mesh_parameters.lsnow_interception_svs2",
                "valid_type": aiida.orm.Bool,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Bool(False),
            },
            {
                "name": "mesh_parameters.cano_ref_forcing",
                "valid_type": aiida.orm.Str,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Str("ABV"),
            },
            {
                "name": "mesh_parameters.VGH_DENS",
                "valid_type": aiida.orm.Float,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Float(0.0),
            },
            {
                "name": "mesh_parameters.HVEGLPOL",
                "valid_type": aiida.orm.Float,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Float(0.2),
            },
            {
                "name": "mesh_parameters.lvar_lmin_stable",
                "valid_type": aiida.orm.Str,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Str("CST"),
            },
            {
                "name": "mesh_parameters.lmin_stable",
                "valid_type": aiida.orm.Float,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Float(10.0),
            },
            {
                "name": "mesh_parameters.lmo_winter",
                "valid_type": aiida.orm.Float,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Float(-1.0),
            },
            {
                "name": "mesh_parameters.lout_snow_profile",
                "valid_type": aiida.orm.Bool,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Bool(False),
            },
            {
                "name": "mesh_parameters.lout_snow_vegh",
                "valid_type": aiida.orm.Bool,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Bool(False),
            },
            {
                "name": "mesh_parameters.nprofile_day",
                "valid_type": aiida.orm.Int,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Int(4),
            },
            {
                "name": "mesh_parameters.lout_snow_enbal",
                "valid_type": aiida.orm.Bool,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Bool(False),
            },
            {
                "name": "mesh_parameters.lout_svs2_watbal",
                "valid_type": aiida.orm.Bool,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Bool(False),
            },
            {
                "name": "mesh_parameters.lout_half_hourly",
                "valid_type": aiida.orm.Bool,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Bool(False),
            },
            {
                "name": "mesh_parameters.lwrite_restart",
                "valid_type": aiida.orm.Bool,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Bool(False),
            },
            {
                "name": "mesh_parameters.lread_restart",
                "valid_type": aiida.orm.Bool,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Bool(False),
            },
            {
                "name": "mesh_parameters.append_text",
                "valid_type": aiida.orm.Str,
                "serializer": aiida.orm.to_aiida_type,
                "required": False,
                "help": (
                    "Optional text to append to the end of the "
                    "MESH_parameters.txt file."
                ),
            },
            {
                "name": "mesh_input_run_options.hourly_flag",
                "valid_type": aiida.orm.Str,
                "serializer": aiida.orm.to_aiida_type,
            },
            {
                "name": "mesh_input_run_options.start_date",
                "valid_type": aiida.orm.Str,
                "serializer": aiida.orm.to_aiida_type,
            },
            {
                "name": "mesh_input_run_options.SHDFILEFLAG",
                "valid_type": aiida.orm.Int,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Int(2),
            },
            {
                "name": "mesh_input_run_options.INPUTPARAMSFORMFLAG",
                "valid_type": aiida.orm.Str,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Str("only txt"),
            },
            {
                "name": "mesh_input_run_options.SOILINIFLAG",
                "valid_type": aiida.orm.Int,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Int(0),
            },
            {
                "name": "mesh_input_run_options.NRSOILAYEREADFLAG",
                "valid_type": aiida.orm.Int,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Int(3),
            },
            {
                "name": "mesh_input_run_options.RUNMODE",
                "valid_type": aiida.orm.Str,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Str("runsvs noroute"),
            },
            {
                "name": "mesh_input_run_options.DIAGNOSEMODE",
                "valid_type": aiida.orm.Str,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Str("on"),
            },
            {
                "name": "mesh_input_run_options.TIMESTEPFLAG",
                "valid_type": aiida.orm.Int,
                "serializer": aiida.orm.to_aiida_type,
                "default": lambda: aiida.orm.Int(10),
            },
        ]:
            if "default" in input_spec:
                input_spec["help"] = " ".join(
                    help_string
                    for help_string in [
                        input_spec.get("help"),
                        "Defaults to ``{default}``.".format(
                            default=input_spec["default"]().value
                        ),
                    ]
                    if help_string
                )
            spec.input(**input_spec)

        spec.output(
            "output",
            valid_type=aiida.orm.RemoteData,
            help="Output directory containing SVS output files.",
        )
        spec.exit_code(
            400,
            "SVS_ERROR",
            message="SVS exited with a non-zero status: {remote_path}",
        )

    def prepare_for_submission(self, folder):

        mesh_parameters = {
            k: {True: ".true.", False: ".false."}[v.value]
            if isinstance(v.value, bool)
            else v.value
            for k, v in self.inputs.mesh_parameters.items()
        }
        mesh_parameters["vf"] = "     ".join(str(f) for f in mesh_parameters["vf"])
        for key in ["sand", "clay", "wsoil", "isoil", "tpsoil"]:
            mesh_parameters[key] = " ".join(str(f) for f in mesh_parameters[key])
        with folder.open("MESH_parameters.txt", "w", encoding="utf8") as file:
            file.write(
                string.Template(
                    (SVS_DATA_DIR / "MESH_parameters.txt.in").read_text()
                ).substitute(mesh_parameters)
            )
            if append_text := mesh_parameters.get("append_text"):
                file.write(f"\n{append_text}\n")

        mesh_input_run_options = {
            k: v.value for k, v in self.inputs.mesh_input_run_options.items()
        }
        with folder.open("MESH_input_run_options.ini", "w", encoding="utf8") as file:
            file.write(
                string.Template(
                    (SVS_DATA_DIR / "MESH_input_run_options.ini.in").read_text()
                ).substitute(mesh_input_run_options)
            )

        mesh_input_soil_levels_delz = self.inputs.mesh_input_soil_levels.delz.get_list()
        mesh_input_soil_levels_dl_svs = (
            self.inputs.mesh_input_soil_levels.dl_svs.get_list()
        )
        with folder.open("MESH_input_soil_levels.txt", "w", encoding="utf8") as file:
            for i, (delz, dl_svs) in enumerate(
                zip(mesh_input_soil_levels_delz, mesh_input_soil_levels_dl_svs)
            ):
                file.write(f"{delz:>10} {dl_svs:>10} !> delz({i})/dl_svs({i})\n")

        codeinfo = aiida.common.datastructures.CodeInfo()
        codeinfo.code_uuid = self.inputs.code.uuid
        codeinfo.stdout_name = "svs.out"
        codeinfo.stderr_name = "svs.err"

        calcinfo = aiida.common.datastructures.CalcInfo()
        calcinfo.codes_info = [codeinfo]
        calcinfo.retrieve_list = ["svs.status"]
        calcinfo.remote_symlink_list = [
            (
                self.inputs.code.computer.uuid,
                self.inputs.basin_humidity.get_remote_path(),
                "basin_humidity.csv",
            ),
            (
                self.inputs.code.computer.uuid,
                self.inputs.basin_longwave.get_remote_path(),
                "basin_longwave.csv",
            ),
            (
                self.inputs.code.computer.uuid,
                self.inputs.basin_pres.get_remote_path(),
                "basin_pres.csv",
            ),
            (
                self.inputs.code.computer.uuid,
                self.inputs.basin_rain.get_remote_path(),
                "basin_rain.csv",
            ),
            (
                self.inputs.code.computer.uuid,
                self.inputs.basin_shortwave.get_remote_path(),
                "basin_shortwave.csv",
            ),
            (
                self.inputs.code.computer.uuid,
                self.inputs.basin_temperature.get_remote_path(),
                "basin_temperature.csv",
            ),
            (
                self.inputs.code.computer.uuid,
                self.inputs.basin_wind.get_remote_path(),
                "basin_wind.csv",
            ),
        ]

        _ = folder.get_subfolder("output", create=True)

        # Capture exit status in status file to inspect later in parser:
        calcinfo.append_text = "echo $? > svs.status"

        return calcinfo
