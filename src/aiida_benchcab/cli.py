import aiida.cmdline.groups
import aiida.cmdline.params
import aiida.engine
import click
import ruamel.yaml

import aiida_benchcab
import aiida_benchcab.workflows
from aiida_benchcab.utils import to_aiida_inputs

yaml = ruamel.yaml.YAML()


@click.group(
    "benchcab",
    cls=aiida.cmdline.groups.VerdiCommandGroup,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.version_option(
    version=aiida_benchcab.__version__, message="aiida-benchcab %(version)s"
)
def cli():
    """Command line interface for aiida-benchcab"""


@click.command("run")
@aiida.cmdline.params.options.PROFILE(
    type=aiida.cmdline.params.types.ProfileParamType(
        load_profile=True,
    ),
    expose_value=False,
)
@click.option(
    "-c",
    "--config",
    type=click.Path(exists=True),
    required=True,
    help="Path to the configuration file.",
)
@click.option(
    "-m",
    "--minimum-job-poll-interval",
    type=click.FLOAT,
    required=False,
    help=(
        "Minimum job poll interval in seconds. If not specified, the default "
        "value for the computer will be used."
    ),
)
@click.option(
    "-d",
    "--daemon",
    is_flag=True,
    default=False,
    show_default=True,
    help="Submit the process to the daemon instead of running it locally.",
)
def run(config, daemon, minimum_job_poll_interval=None):
    """Run the flux tower workflow from a configuration file."""

    with open(config, "r") as f:
        inputs = yaml.load(f)

    try:
        computer = aiida.orm.load_computer(inputs["computer"])
    except KeyError:
        raise click.ClickException(
            f"The configuration file '{config}' does not contain a 'computer' key."
        )
    except aiida.common.NotExistent:
        raise click.ClickException(
            f"Computer '{inputs['computer']}' does not exist in the AiiDA database."
        )

    if minimum_job_poll_interval is not None:
        computer.set_minimum_job_poll_interval(minimum_job_poll_interval)

    inputs = to_aiida_inputs(inputs, computer=computer)

    if daemon:
        node = aiida.engine.submit(
            aiida_benchcab.workflows.FluxTowerWorkChain, **inputs
        )
        click.echo(
            "Submitted "
            f"{aiida_benchcab.workflows.FluxTowerWorkChain.__name__}<{node.pk}> to "
            "the daemon"
        )
    else:
        _, node = aiida.engine.launch.run_get_node(
            aiida_benchcab.workflows.FluxTowerWorkChain, **inputs
        )
        if not node.is_finished_ok:
            raise click.ClickException(
                f"Workflow failed with message: {node.exit_message}"
            )


cli.add_command(run)
