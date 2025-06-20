import importlib
import sys
import types
import pytest
from pathlib import Path

if "torch" not in sys.modules:
    sys.modules["torch"] = types.SimpleNamespace(float16="fp16", bfloat16="bf16", float32="fp32")

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
tfm = types.ModuleType("transformers")
tfm.AutoConfig = object
tfm.PretrainedConfig = object
tfm.AutoModelForCausalLM = types.SimpleNamespace(from_pretrained=lambda *a, **k: None)
tfm.AutoTokenizer = types.SimpleNamespace(from_pretrained=lambda *a, **k: None)
tfm.TextIteratorStreamer = object
class _BitsAndBytesConfig:
    def __init__(self, *a, **k):
        pass

tfm.BitsAndBytesConfig = _BitsAndBytesConfig
sys.modules.setdefault("transformers", tfm)
sys.modules.setdefault("transformers.integrations", types.ModuleType("integrations"))
bnb_mod = types.ModuleType("bitsandbytes")
bnb_mod._validate_bnb_multi_backend_availability = lambda *a, **k: None
sys.modules["transformers.integrations.bitsandbytes"] = bnb_mod
import transqlate.utils.hardware  # ensure module is loadable

def test_cpu_opt_out(monkeypatch):
    monkeypatch.setenv("TRANSQLATE_NO_QUANT", "1")
    from transqlate.utils.hardware import detect_device_and_quant
    dm, dt, q = detect_device_and_quant(True)
    assert q is False


def test_error_on_bnb_failure(monkeypatch, mocker):
    import torch
    mocker.patch(
        "transqlate.utils.hardware.detect_device_and_quant",
        return_value=("auto", torch.float16, True),
    )
    import transqlate.inference as inf

    mock_model = mocker.patch(
        "transformers.AutoModelForCausalLM.from_pretrained",
        side_effect=RuntimeError("bitsandbytes"),
    )

    class DummyTok:
        eos_token = ""
        pad_token = ""

    mocker.patch("transformers.AutoTokenizer.from_pretrained", return_value=DummyTok())
    with pytest.raises(RuntimeError):
        inf.NL2SQLInference(model_dir="dummy")
    assert mock_model.call_count == 1


def test_error_on_pkg_missing(monkeypatch, mocker):
    import torch
    mocker.patch(
        "transqlate.utils.hardware.detect_device_and_quant",
        return_value=("auto", torch.float16, True),
    )
    import transqlate.inference as inf

    mock_model = mocker.patch(
        "transformers.AutoModelForCausalLM.from_pretrained",
        side_effect=importlib.metadata.PackageNotFoundError("bitsandbytes"),
    )

    class DummyTok:
        eos_token = ""
        pad_token = ""

    mocker.patch("transformers.AutoTokenizer.from_pretrained", return_value=DummyTok())
    with pytest.raises(importlib.metadata.PackageNotFoundError):
        inf.NL2SQLInference(model_dir="dummy")
    assert mock_model.call_count == 1


def test_error_with_quant_attr(monkeypatch, mocker):
    import torch
    mocker.patch(
        "transqlate.utils.hardware.detect_device_and_quant",
        return_value=("auto", torch.float16, True),
    )
    import transqlate.inference as inf

    mock_model = mocker.patch(
        "transformers.AutoModelForCausalLM.from_pretrained",
        side_effect=importlib.metadata.PackageNotFoundError("bitsandbytes"),
    )

    class DummyConfig:
        quantization_config = object()

        def to_dict(self):
            return {}

        @classmethod
        def from_dict(cls, *a, **k):
            return cls()

    monkeypatch.setattr(
        tfm,
        "AutoConfig",
        types.SimpleNamespace(
            from_pretrained=lambda *a, **k: DummyConfig(),
        ),
    )

    class DummyTok:
        eos_token = ""
        pad_token = ""

    mocker.patch("transformers.AutoTokenizer.from_pretrained", return_value=DummyTok())
    with pytest.raises(importlib.metadata.PackageNotFoundError):
        inf.NL2SQLInference(model_dir="dummy")
    assert mock_model.call_count == 1


def test_runtime_error_on_cpu(monkeypatch, mocker):
    import torch
    mocker.patch(
        "transqlate.utils.hardware.detect_device_and_quant",
        return_value=("cpu", torch.float32, False),
    )
    import transqlate.inference as inf

    mock_model = mocker.patch(
        "transformers.AutoModelForCausalLM.from_pretrained",
        side_effect=RuntimeError("bitsandbytes"),
    )

    class DummyTok:
        eos_token = ""
        pad_token = ""

    mocker.patch("transformers.AutoTokenizer.from_pretrained", return_value=DummyTok())
    with pytest.raises(RuntimeError):
        inf.NL2SQLInference(model_dir="dummy")
    assert mock_model.call_count == 1
