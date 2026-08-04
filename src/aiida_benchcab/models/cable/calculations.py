import aiida.engine
import aiida.orm
import f90nml

from aiida_benchcab.utils import deep_update

from .utils import get_remote_content, get_remote_filename


class CableCalculation(aiida.engine.CalcJob):
    """Calculation plugin for running CABLE."""

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
            default="benchcab.models.cable_parser",
        )
        spec.input(
            "cable_namelist",
            valid_type=aiida.orm.RemoteData,
            help=(
                "CABLE namelist file. Note that some options in the namelist "
                "file may be overriden when running the calculation. Please see "
                "the ``cable_namelist_patch`` input and the "
                "``prepare_for_submission`` method of ``CableCalculation`` for "
                "details."
            ),
        )
        spec.input(
            "cable_pft_namelist",
            valid_type=aiida.orm.RemoteData,
            help="CABLE PFT parameters namelist file.",
        )
        spec.input(
            "cable_soil_namelist",
            valid_type=aiida.orm.RemoteData,
            help="CABLE soil parameters namelist file.",
        )
        spec.input(
            "cable_met_file",
            valid_type=aiida.orm.RemoteData,
            help="CABLE meteorological forcing file.",
        )
        spec.input(
            "cable_gridinfo_file",
            valid_type=aiida.orm.RemoteData,
            help="CABLE gridinfo file.",
        )
        spec.input(
            "cable_namelist_patch",
            valid_type=aiida.orm.Dict,
            required=False,
            serializer=aiida.orm.to_aiida_type,
            help=(
                "Optional patch to apply to the main CABLE namelist file. "
                "Namelist options are specified as a python dictionary and are "
                "applied to the namelist file."
            ),
        )
        spec.input(
            "cable_output_filename",
            valid_type=aiida.orm.Str,
            serializer=aiida.orm.to_aiida_type,
            help="The name of the CABLE output file.",
        )

        spec.output(
            "cable_output_file",
            valid_type=aiida.orm.RemoteData,
            help="The CABLE netCDF output file.",
        )

        spec.exit_code(
            400,
            "CABLE_ERROR",
            message="CABLE exited with a non-zero status: {remote_path}",
        )

    def prepare_for_submission(self, folder):

        codeinfo = aiida.common.datastructures.CodeInfo()
        codeinfo.code_uuid = self.inputs.code.uuid
        codeinfo.stdout_name = "cable.out"
        codeinfo.stderr_name = "cable.err"

        calcinfo = aiida.common.datastructures.CalcInfo()
        calcinfo.codes_info = [codeinfo]
        calcinfo.retrieve_list = ["cable.status"]
        calcinfo.remote_symlink_list = []

        # Capture exit status in status file to inspect later in parser:
        calcinfo.append_text = "echo $? > cable.status"

        for file in [
            self.inputs.cable_met_file,
            self.inputs.cable_gridinfo_file,
            self.inputs.cable_pft_namelist,
            self.inputs.cable_soil_namelist,
        ]:
            calcinfo.remote_symlink_list.append(
                (file.computer.uuid, file.get_remote_path(), get_remote_filename(file))
            )

        cable_nml = f90nml.reads(get_remote_content(self.inputs.cable_namelist))

        if "cable_namelist_patch" in self.inputs:
            cable_nml = deep_update(
                cable_nml, self.inputs.cable_namelist_patch.get_dict()
            )

        cable_nml["cable"]["filename"]["met"] = get_remote_filename(
            self.inputs.cable_met_file
        )
        cable_nml["cable"]["filename"]["type"] = get_remote_filename(
            self.inputs.cable_gridinfo_file
        )
        cable_nml["cable"]["filename"]["log"] = "log_cable.txt"
        cable_nml["cable"]["filename"]["out"] = self.inputs.cable_output_filename.value
        cable_nml["cable"]["output"]["patch"] = False

        with folder.open("cable.nml", "w", encoding="utf8") as handle:
            f90nml.write(cable_nml, handle)

        return calcinfo
