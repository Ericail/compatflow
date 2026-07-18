from pathlib import Path

from compatflow.capture.models import ExperimentManifest


ROOT = Path(__file__).parents[2]


def test_all_experiment_manifests_validate() -> None:
    paths = sorted((ROOT / "experiments").rglob("*.json"))
    assert paths

    manifests = [
        ExperimentManifest.model_validate_json(path.read_text(encoding="utf-8"))
        for path in paths
    ]

    assert len({manifest.experiment_id for manifest in manifests}) == len(manifests)
    assert len({manifest.trace_id for manifest in manifests}) == len(manifests)


def test_vllm_16340_pair_has_opposite_wire_expectations() -> None:
    directory = ROOT / "experiments" / "vllm_16340"
    affected = ExperimentManifest.model_validate_json(
        (directory / "affected.json").read_text(encoding="utf-8")
    )
    fixed = ExperimentManifest.model_validate_json(
        (directory / "fixed.json").read_text(encoding="utf-8")
    )

    assert affected.request == fixed.request
    assert affected.wire_expectation.outcome == "noncompliant"
    assert fixed.wire_expectation.outcome == "compliant"
    assert affected.server.source_ref == "v0.8.3"
    assert fixed.server.source_ref == "05a4324"
