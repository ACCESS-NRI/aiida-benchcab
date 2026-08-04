import importlib.resources
import pathlib
from typing import Any, TypeVar

import aiida.common.log
import aiida.orm
import ruamel.yaml

logger = aiida.common.log.AIIDA_LOGGER.getChild(__name__)

# fmt: off
# ======================================================
# Copyright (c) 2017 - 2022 Samuel Colvin and other contributors
# from https://github.com/pydantic/pydantic/blob/fd2991fe6a73819b48c906e3c3274e8e47d0f761/pydantic/utils.py#L200

KeyType = TypeVar('KeyType')


def deep_update(mapping: dict[KeyType, Any], *updating_mappings: dict[KeyType, Any]) -> dict[KeyType, Any]:
    updated_mapping = mapping.copy()
    for updating_mapping in updating_mappings:
        for k, v in updating_mapping.items():
            if k in updated_mapping and isinstance(updated_mapping[k], dict) and isinstance(v, dict):
                updated_mapping[k] = deep_update(updated_mapping[k], v)
            else:
                updated_mapping[k] = v
    return updated_mapping

# ======================================================
# fmt: on


def get_installed_root():
    return pathlib.Path(importlib.resources.files("aiida_benchcab"))


def load_remote_data(remote_path, computer, check_file_hash=True):
    remote_data_filters = {}
    remote_data_filters["attributes.remote_path"] = remote_path
    if check_file_hash:
        with computer.get_transport() as transport:
            return_code, stdout, stderr = transport.exec_command_wait(
                f"sha256sum {remote_path}"
            )
            if return_code == 0:
                remote_data_filters["extras.sha256"] = stdout.strip()
            elif transport.isdir(remote_path):
                pass
            else:
                raise RuntimeError(
                    f"Failed to compute sha256 hash for file '{remote_path}' on "
                    f"computer Computer<{computer.label}>: {stdout=} {stderr=}"
                )
    qb = aiida.orm.QueryBuilder()
    qb.append(
        aiida.orm.Computer,
        tag="computer",
        filters={"uuid": computer.uuid},
    ).append(
        aiida.orm.RemoteData,
        with_computer="computer",
        filters=remote_data_filters,
    )
    if node := qb.first(flat=True):
        logger.debug(
            f"Reusing RemoteData<{node.pk}> for Computer<{computer.label}> with "
            f"remote path {remote_path}"
        )
        return node
    else:
        node = aiida.orm.RemoteData(remote_path=remote_path, computer=computer)
        if "extras.sha256" in remote_data_filters:
            node.base.extras.set("sha256", remote_data_filters["extras.sha256"])
        return node


def load_singlefile_data(
    path=None, from_string=None, from_bytes=None, check_file_hash=True
):
    if path:
        node = aiida.orm.SinglefileData(path)
    elif from_string:
        node = aiida.orm.SinglefileData.from_string(from_string)
    elif from_bytes:
        node = aiida.orm.SinglefileData.from_bytes(from_bytes)
    else:
        raise ValueError(
            "Either `path`, `from_string`, or `from_bytes` must be provided."
        )
    if check_file_hash:
        qb = aiida.orm.QueryBuilder()
        qb.append(
            aiida.orm.SinglefileData,
            filters={"extras._aiida_hash": node.base.caching._compute_hash()},
        )
        if existing := qb.first(flat=True):
            node = existing
    return node


def _load_aiida_node_from_tag(v: ruamel.yaml.comments.TaggedScalar, **kwargs):
    if v._yaml_tag == "!RemoteData":
        return load_remote_data(remote_path=v.value, computer=kwargs["computer"])
    else:
        raise ValueError(f"Unsupported YAML tag: {v._yaml_tag}")


def to_aiida_inputs(inputs, **kwargs):
    updated_inputs = inputs.copy()
    for k, v in updated_inputs.items():
        if isinstance(v, ruamel.yaml.comments.TaggedScalar):
            updated_inputs[k] = _load_aiida_node_from_tag(v, **kwargs)
        elif isinstance(v, dict):
            updated_inputs[k] = to_aiida_inputs(v, **kwargs)
        elif isinstance(v, list):
            updated_inputs[k] = [
                _load_aiida_node_from_tag(item, **kwargs)
                if isinstance(item, ruamel.yaml.comments.TaggedScalar)
                else to_aiida_inputs(item, **kwargs)
                if isinstance(item, dict)
                else item
                for item in v
            ]
    return updated_inputs
