import json
import time
from pathlib import Path

import pytest
from pystarport.ports import rpc_port

from .utils import cluster_fixture, wait_for_new_blocks, wait_for_port


# use custom cluster, use an unique base port
@pytest.fixture(scope="module")
def fork(worker_index, pytestconfig, tmp_path_factory):
    "override cluster fixture for this test module"
    yield from cluster_fixture(
        Path(__file__).parent / "configs/slash_fork.jsonnet",
        worker_index,
        tmp_path_factory.mktemp("data"),
    )


@pytest.fixture(scope="module")
def bug(worker_index, pytestconfig, tmp_path_factory):
    "override cluster fixture for this test module"
    yield from cluster_fixture(
        Path(__file__).parent / "configs/slash_bug.jsonnet",
        worker_index,
        tmp_path_factory.mktemp("data"),
    )


def exec(cluster, has_slash):
    signer1_address = cluster.address("signer1", i=0)
    balance = cluster.balance(signer1_address)
    validators = list(
        map(
            lambda i: i["operator_address"],
            sorted(
                cluster.validators(),
                key=lambda i: i["description"]["moniker"],
            ),
        ),
    )
    validator2_operator_address = validators[2]
    validator1_operator_address = validators[1]
    delegate = 300
    rsp = cluster.delegate_amount(
        validator2_operator_address, f"{delegate}basecro", signer1_address
    )
    assert rsp["code"] == 0, rsp["raw_log"]
    balance -= delegate
    assert balance == cluster.balance(signer1_address)
    delegate = 400
    rsp = cluster.delegate_amount(
        validator1_operator_address, f"{delegate}basecro", signer1_address
    )
    assert rsp["code"] == 0, rsp["raw_log"]
    balance -= delegate
    assert balance == cluster.balance(signer1_address)

    def print_status():
        balance = cluster.balance(signer1_address)
        print(f"signer1: {signer1_address}, balance: {balance}")
        bonded = cluster.staking_pool()
        unbonded = cluster.staking_pool(False)
        print(f"bonded: {bonded}, unbonded: {unbonded}")
        v = cluster.validator(validator2_operator_address)
        print(f'v2: {validator2_operator_address}, {v["jailed"]}, token: {v["tokens"]}')
        v = cluster.validator(validator1_operator_address)
        print(f'v1: {validator1_operator_address}, {v["jailed"]}, token: {v["tokens"]}')

    print_status()
    unbond = 100
    rsp = cluster.unbond_amount(
        validator1_operator_address, f"{unbond}basecro", signer1_address
    )
    assert rsp["code"] == 0, rsp
    cli = cluster.cosmos_cli()
    redelegate = 200
    rsp = json.loads(
        cli.raw(
            "tx",
            "staking",
            "redelegate",
            validator2_operator_address,
            validator1_operator_address,
            f"{redelegate}basecro",
            "-y",
            "--gas",
            "300000",
            home=cli.data_dir,
            from_=signer1_address,
            keyring_backend="test",
            chain_id=cli.chain_id,
            node=cli.node_rpc,
        )
    )
    assert rsp["code"] == 0, rsp["raw_log"]
    print("stop node2 and wait for 3 blocks for non-live slashing")
    print_status()
    assert balance == cluster.balance(signer1_address)
    i = 2
    cluster.supervisor.stopProcess(f"{cluster.chain_id}-node{i}")
    wait_for_new_blocks(cluster, 3, i=1)
    cluster.supervisor.startProcess(f"{cluster.chain_id}-node{i}")
    wait_for_port(rpc_port(cluster.base_port(i)))
    time.sleep(5)
    print_status()
    slash_amt = 0
    if has_slash:
        slash_amt = redelegate * 0.1
    balance += unbond
    assert balance - slash_amt == cluster.balance(signer1_address)


@pytest.mark.slow
def test_slash_bug(bug):
    exec(bug, False)


@pytest.mark.slow
def test_slash_fork(fork):
    exec(fork, True)
