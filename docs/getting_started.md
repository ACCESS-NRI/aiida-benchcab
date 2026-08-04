# Getting Started

## Installing

`aiida-benchcab` can be installed with the following ways:

::::{tab-set}

:::{tab-item} pip
    pip install aiida-benchcab
:::

:::{tab-item} conda
    conda install -c accessnri aiida-benchcab
:::

::::

We recommended that `aiida-benchcab` is installed on your local computer,
regardless of the machine where you intend to run your model. For example, if
you want to run computations on a HPC cluster, AiiDA will interact with the
cluster remotely via `ssh`. More information on setting up a HPC cluster with
AiiDA can be found below in the [Prerequisites](#prerequisites) section.

## Running the Flux Tower Evaluation Workflow

In this section we describe how to run the
[FluxTowerWorkChain][flux-tower-work-chain] for running and evaluating land
surface models driven using eddy covariance observations.

### Prerequisites

To run the flux tower evaluation workflow, you will need to have the following:

1. **A configured AiiDA profile on the machine where `aiida-benchcab` is
installed:** Note that the `aiida-core` package will be installed with
`aiida-benchcab` as a dependency. Please follow the [installation
guide][aiida-profile-setup] to setup a profile. We recommend starting with the
[quick installation][aiida-quick-installation] first before trying the
[complete installation][aiida-complete-installation].
2. **An account on [modelevaluation.org][modelevaluation]:** See
[registration](https://modelevaluation.org/registration) to create an account.
After creating an account, please join the **benchcab-evaluation** workspace
(see [workspaces](https://modelevaluation.org/workspaces)).
3. **Access to a computer where you can run your model:** The target computer
where you wish to run your model can be your local machine or a HPC cluster. For
more information on configuring a computer with AiiDA, see *[How to set up a
computer][aiida-computer-setup]*.

    ```{note}
    For users who wish to run computations on the **NCI Gadi HPC cluster**, please
    install the [aiida-gadi-scheduler][aiida-gadi-scheduler] plugin and follow the
    instructions in the [README][aiida-gadi-scheduler-readme] to setup and configure
    Gadi with AiiDA.
    ```

    The target model must be supported by `aiida-benchcab` - see
    [here](workflow_reference/flux_tower.md) for more information on the
    currently supported models. A list of supported models can also be found by
    listing the available plugin entry points for the flux tower workflow by
    running the following command after `aiida-benchcab` is installed:

    ```shell
    verdi plugin list aiida.workflows | grep benchcab.flux_tower
    ```

4. **An install of [meorg_client][meorg_client] on the target computer:**
`meorg_client` is available to install via [pypi][meorg_client-pypi] or
[conda][meorg_client-conda]. You will then need to follow [these
instructions][meorg_client-credentials] to authenticate your credentials.
5. **Installed dependencies and input files on the target computer:** At a
minimum you will need:

    1. An installation of flux tower forcing data sets provided in the [*Forty
    two site test* experiment][forty-two-site-test]. Please download all
    datasets onto the target computer and expand the zipfile so that each
    individual dataset can be read. Each dataset should belong in a common
    directory with their file name unchanged.

    2. An installation of the input files and software packages required to run
    the model of interest on the target computer. Please refer to the
    documentation on [Model Specific
    Workflows](workflow_reference/flux_tower.md#model-specific-workflows) for
    more information on the required input files and software packages to run
    the model specific workflow.

### Running the Mock CABLE Flux Tower Workflow

A mock workflow for the CABLE land surface model is provided as a way to verify
your installation is working correctly. The workflow does not require any model
specific input files, and can be launched either via the `benchcab` command line
tool, or as a python script:

::::{tab-set}

:::{tab-item} CLI
```shell
benchcab run -c cable-mock.yaml
```

where the workflow configuration file (`cable-mock.yaml`) contains:

```yaml
computer: localhost
site_meteorology_path: !RemoteData /path/to/model/forcing/data
experiment: AU-Tum
model_inputs:
  workflow_plugin: benchcab.flux_tower.cable_mock
meorg:
  output_name: my-model-output
  skip_upload: True
```

:::

:::{tab-item} Python

```python
import aiida
import aiida.orm
import aiida.engine

import aiida_benchcab.workflows

aiida.load_profile()

computer = aiida.orm.load_computer("localhost")

results = aiida.engine.run(
    aiida_benchcab.workflows.FluxTowerWorkChain,
    **{
        "computer": computer,
        "site_meteorology_path": aiida.orm.RemoteData(
            remote_path="/path/to/model/forcing/data", computer=computer
        ),
        "experiment": "AU-Tum",
        "model_inputs": {
            "workflow_plugin": "benchcab.flux_tower.cable_mock",
        },
        "meorg": {
            "output_name": "my-model-output",
            "skip_upload": True,
        }
    }
)

:::

::::

For more information on the available options, please refer to the [Flux Tower
Workflow][flux-tower] reference.

Running the above examples should produce output similar to the following:

```
Report: [32|FluxTowerWorkChain|flux_tower_init]: Setting up workflow...
Report: [32|FluxTowerWorkChain|flux_tower_init]: tasks: 1 (sites: 1, realisations: 1, science_configurations: 1)
Report: [32|FluxTowerWorkChain|flux_tower_tasks_run]: Submitting task: AU-Tum_cable_R0_S0 (pk: 39)
Report: [32|FluxTowerWorkChain|flux_tower_tasks_inspect]: 0 failed, 1 passed
Report: [32|FluxTowerWorkChain|flux_tower_meorg_upload]: Skipping upload to modelevaluation.org
```

The above example can be modified to trigger the flux tower analysis on
[modelevaluation.org][modelevaluation] by setting `meorg.skip_upload` to
`False`. Depending on how `meorg_client` is installed, this may require
additional inputs to be specified which allow `aiida-benchcab` to run the
`meorg` command line tool. Please refer to the documentation on the `meorg`
input namespace of the [FluxTowerWorkChain][flux-tower-work-chain] for more
information on configuring this part of the workflow.

### Examples

For real world examples, please see the example configurations provided in the
[aiida-benchcab repository][aiida-benchcab-flux-tower-examples].

[flux-tower]: workflow_reference/flux_tower.md
[flux-tower-work-chain]: workflow_reference/flux_tower.md#fluxtowerworkchain
[pip]: https://pip.pypa.io/en/stable/
[aiida-profile-setup]: https://aiida.readthedocs.io/projects/aiida-core/en/stable/installation/index.html
[aiida-quick-installation]: https://aiida.readthedocs.io/projects/aiida-core/en/stable/installation/guide_quick.html
[aiida-complete-installation]: https://aiida.readthedocs.io/projects/aiida-core/en/stable/installation/guide_complete.html
[aiida-computer-setup]: https://aiida.readthedocs.io/projects/aiida-core/en/stable/howto/run_codes.html#how-to-set-up-a-computer
[aiida-benchcab-flux-tower-examples]: https://github.com/ACCESS-NRI/aiida-benchcab/blob/main/examples/flux_tower
[aiida-gadi-scheduler]: https://github.com/ACCESS-NRI/aiida-gadi-scheduler
[aiida-gadi-scheduler-readme]: https://github.com/ACCESS-NRI/aiida-gadi-scheduler/blob/main/README.md
[modelevaluation]: https://modelevaluation.org/
[meorg_client]: https://meorg-client.readthedocs.io/en/latest/
[meorg_client-credentials]: https://meorg-client.readthedocs.io/en/latest/cli/#set-up-credentials
[meorg_client-conda]: https://anaconda.org/channels/accessnri/packages/meorg_client/overview
[meorg_client-pypi]: https://pypi.org/project/meorg_client/
[forty-two-site-test]: https://modelevaluation.org/experiment/display/s6k22L3WajmiS9uGv
