import pathlib

import aiida

from .calculations import CableCalculation


class CableParser(aiida.parsers.parser.Parser):
    """Parser plugin for CABLE output."""

    def __init__(self, node):
        super().__init__(node)
        if not issubclass(node.process_class, CableCalculation):
            raise aiida.common.exceptions.ParsingError(
                "Can only parse CableCalculation"
            )

    def parse(self, **kwargs):
        """Parse the contents of the output files retrieved in the `FolderData`."""

        work_path = pathlib.PurePosixPath(self.node.get_remote_workdir())

        if self._exit_status() != 0:
            return self.exit_codes.CABLE_ERROR.format(remote_path=work_path)

        self.out(
            "cable_output_file",
            aiida.orm.RemoteData(
                computer=self.node.computer,
                remote_path=str(
                    work_path / self.node.inputs.cable_output_filename.value
                ),
            ),
        )

    def _exit_status(self):
        return int(self.retrieved.get_object_content("cable.status"))
