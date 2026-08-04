import pathlib

import aiida

from .calculations import SVSCalculation


class SVSParser(aiida.parsers.parser.Parser):
    """Parser plugin for the MESH-SVS code output."""

    def __init__(self, node):
        super().__init__(node)
        if not issubclass(node.process_class, SVSCalculation):
            raise aiida.common.exceptions.ParsingError("Can only parse SVSCalculation")

    def parse(self, **kwargs):
        """Parse the contents of the output files retrieved in the `FolderData`."""

        work_path = pathlib.PurePosixPath(self.node.get_remote_workdir())

        if self._exit_status() != 0:
            return self.exit_codes.SVS_ERROR.format(remote_path=work_path)

        self.out(
            "output",
            aiida.orm.RemoteData(
                computer=self.node.computer, remote_path=str(work_path / "output")
            ),
        )

    def _exit_status(self):
        return int(self.retrieved.get_object_content("svs.status"))
