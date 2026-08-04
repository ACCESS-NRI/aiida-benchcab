"""Script for converting common flux tower forcing data to SVS input files.

The common flux tower forcing data in NetCDF format is read and unpacked into
individual CSV files for use with SVS. Additional input overrides for configuring
SVS are extracted from the common flux tower forcing input file and are written
to a json file.
"""

import json
import pathlib
import sys

import xarray

if len(sys.argv) != 2:
    print(f"Usage: python {pathlib.Path(__file__).name} <file_path>", file=sys.stderr)
    sys.exit(1)

ds = xarray.open_dataset(sys.argv[1])
df = ds.to_dataframe()

svs_met_inputs = json.loads(pathlib.Path("input_variable_to_basin_file.json").read_text())

for variable, file in svs_met_inputs.items():
    df[variable].to_csv(file, lineterminator=",\n", index=False, header=False)

igbp_veg_type = ds.IGBP_veg_short.astype(str).values.item().strip()

igbp_to_svs_land_cover = json.loads(
    pathlib.Path("igbp_to_svs_land_cover.json").read_text()
)

height_above_canopy = ds.reference_height.values.item() - ds.canopy_height.values.item()

time_step = ds.time.diff("time")[0]

# Convert to minutes
hourly_flag = int((time_step.dt.total_seconds() / 60.0).values.item())

start_time = df.index.get_level_values("time")[0]

with open("input_overrides.json", "w") as f:
    json.dump(
        {
            "mesh_parameters": {
                "deglat": ds.latitude.values.item(),
                "deglng": ds.longitude.values.item(),
                # Assume reference height of forcing data for momentum (zusl) and reference
                # height of forcing data for temperature and humidity (ztsl) are the same:
                "zusl": height_above_canopy,
                "ztsl": height_above_canopy,
                "vf": [
                    1.0
                    if igbp_to_svs_land_cover["mapping"].get(igbp_veg_type) == i
                    else 0.0
                    for i in range(
                        1, igbp_to_svs_land_cover["n_svs_land_cover_types"] + 1
                    )
                ],
                "lout_half_hourly": hourly_flag == 30,
            },
            "mesh_input_run_options": {
                "hourly_flag": str(hourly_flag),
                "start_date": start_time.strftime("%Y%m%d%H%M"),
            },
        },
        f,
        indent=4,
    )
