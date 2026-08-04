# Flux Tower Workflow

This workflow runs one or more land surface model configurations, with each
configuration driven using several eddy covariance based flux tower
observations. The model output from all simulations is then used to recreate the
PLUMBER2 land model evaluation by uploading the model output to the relevant
experiment on [modelevaluation.org][modelevaluation] via
[`meorg_client`][meorg_client].

This workflow calls land model specific sub-workflows to run the model of
interest. These sub-workflows:

1. Translate the common input forcing data into the format required by the model
2. Run the model
3. Provide the model output as a single NetCDF file in a format suitable for analysis.

See [Model Specific Workflows](#model-specific-workflows) for more details.

The specific flux towers used to drive the ensemble of simulations is currently
limited to several experiment types. Please refer to the `experiment` input of
[FluxTowerWorkChain](#fluxtowerworkchain) for more information on the supported
experiments.

```{contents}
```

## FluxTowerWorkChain

```{eval-rst}
.. aiida-workchain:: FluxTowerWorkChain
   :module: aiida_benchcab.workflows
```

## FluxTowerBaseWorkChain

```{eval-rst}
.. aiida-workchain:: FluxTowerBaseWorkChain
   :module: aiida_benchcab.workflows
```

## Model Specific Workflows

### CABLE Mock

```{eval-rst}
.. aiida-workchain:: MockCableFluxTowerWorkChain
   :module: aiida_benchcab.models.cable.workflows
```

### CABLE

```{eval-rst}
.. aiida-workchain:: CableFluxTowerWorkChain
   :module: aiida_benchcab.models.cable.workflows
```

### SVS

```{eval-rst}
.. aiida-workchain:: SVSFluxTowerWorkChain
   :module: aiida_benchcab.models.svs.workflows
```

[modelevaluation]: https://modelevaluation.org/
[meorg_client]: https://meorg-client.readthedocs.io/en/latest/
