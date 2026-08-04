#!/usr/bin/env bash

# Upload script for modelevaluation.org

set -e

: ${MEORG_UPLOAD_OUTPUT_NAME:?}
: ${MEORG_UPLOAD_EXPERIMENT_ID:?}
: ${MEORG_UPLOAD_MODEL_PROFILE_ID:?}
: ${MEORG_UPLOAD_DATA_DIR:?}
: ${MEORG_UPLOAD_BENCHMARK_IDS:=}
: ${MEORG_UPLOAD_FORCE:=0}
: ${MEORG_UPLOAD_NUM_THREADS:=1}
: ${MEORG_UPLOAD_CACHE_DELAY:=300}
: ${MEORG_UPLOAD_SUMMARY_FILE:=summary.yaml}
: ${MEORG_BASE_URL:=https://modelevaluation.org}

if MODEL_OUTPUT_ID=$(meorg output query --name ${MEORG_UPLOAD_OUTPUT_NAME} 2> /dev/null); then
    echo "Model output exists"
    if [ ${MEORG_UPLOAD_FORCE} -eq 0 ]; then
        echo "Set MEORG_UPLOAD_FORCE=1 to delete existing files and re-run analysis on the same model output ID"
        exit 1
    fi
    echo "Deleting existing files from model output ID"
    meorg file delete_all ${MODEL_OUTPUT_ID}
else
    echo "Creating model output with name ${MEORG_UPLOAD_OUTPUT_NAME}..."
    MODEL_OUTPUT_ID=$( \
        meorg output create \
            --state-selection default \
            --parameter-selection automated \
            --is-bundle \
            ${MEORG_UPLOAD_MODEL_PROFILE_ID} \
            ${MEORG_UPLOAD_OUTPUT_NAME} \
        | head -n 1 \
        | awk '{print $NF}' \
    )
fi

echo "Add experiments to model output"
meorg experiment update ${MODEL_OUTPUT_ID} ${MEORG_UPLOAD_EXPERIMENT_ID}

if [[ -n "${MEORG_UPLOAD_BENCHMARK_IDS}" ]]; then
    echo "Add benchmarks to model output"
    meorg benchmark update ${MODEL_OUTPUT_ID} ${MEORG_UPLOAD_EXPERIMENT_ID} ${MEORG_UPLOAD_BENCHMARK_IDS}
fi

echo "Uploading files to ${MEORG_UPLOAD_OUTPUT_NAME} (ID: ${MODEL_OUTPUT_ID})"
meorg file upload -n ${MEORG_UPLOAD_NUM_THREADS} ${MEORG_UPLOAD_DATA_DIR}/*.nc ${MODEL_OUTPUT_ID}

echo "Waiting for object store transfer (${MEORG_UPLOAD_CACHE_DELAY} sec)"
sleep ${MEORG_UPLOAD_CACHE_DELAY}

echo "Triggering analysis on ${MODEL_OUTPUT_ID}"
ANALYSIS_ID=$(meorg analysis start ${MODEL_OUTPUT_ID} ${MEORG_UPLOAD_EXPERIMENT_ID})

echo "Files transferred to me.org. Analysis in progress."

cat << EOF > ${MEORG_UPLOAD_SUMMARY_FILE}
base_url: ${MEORG_BASE_URL}
model_output_id: ${MODEL_OUTPUT_ID}
analysis_id: ${ANALYSIS_ID}
model_output_name: ${MEORG_UPLOAD_OUTPUT_NAME}
model_output_url: ${MEORG_BASE_URL}/modelOutput/display/${MODEL_OUTPUT_ID}
model_analysis_url: ${MEORG_BASE_URL}/analysis/${ANALYSIS_ID}
model_profile_id: ${MEORG_UPLOAD_MODEL_PROFILE_ID}
experiment_id: ${MEORG_UPLOAD_EXPERIMENT_ID}
benchmark_ids: [${MEORG_UPLOAD_BENCHMARK_IDS}]
data_dir: ${MEORG_UPLOAD_DATA_DIR}
force: $(((${MEORG_UPLOAD_FORCE})) && echo "True" || echo "False")
EOF
