"""Benchmark manifest loader."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


BENCHMARKS_DIR = Path(__file__).parent.parent.parent / "benchmarks"


@dataclass
class ModelAsset:
    filename: str
    size_gib: float
    url: str = ""
    sha256: str = ""
    license: str = "open"           # "open", "gated", "user_supplied"


@dataclass
class BenchmarkPreset:
    id: str
    label: str
    category: str                   # "ml", "rendering", "hpc"
    family: str                     # "llama_cpp", "blender", etc.
    description: str = ""
    model: ModelAsset | None = None
    executable: str = "llama-bench"
    args: list[str] = field(default_factory=list)
    expected_vram_gib: float = 0.0
    repo_compatible: bool = True
    tags: list[str] = field(default_factory=list)

    @property
    def fits_in_vram(self, vram_gib: float = 32.0) -> bool:
        if self.model is None:
            return True
        return self.model.size_gib * 1.2 < vram_gib  # 20% overhead estimate

    def build_command(self, model_path: str) -> list[str]:
        cmd = [self.executable]
        for arg in self.args:
            cmd.append(arg.replace("{model}", model_path))
        return cmd


def load_manifests(category: str | None = None) -> list[BenchmarkPreset]:
    """Load all benchmark presets from YAML files in benchmarks/."""
    presets: list[BenchmarkPreset] = []
    search_dir = BENCHMARKS_DIR
    if not search_dir.exists():
        return presets

    pattern = "**/*.yaml"
    for yaml_file in sorted(search_dir.glob(pattern)):
        try:
            data = yaml.safe_load(yaml_file.read_text())
            if not isinstance(data, dict):
                continue
            benchmarks = data.get("benchmarks", [data])
            for b in benchmarks:
                preset = _parse_preset(b)
                if preset and (category is None or preset.category == category):
                    presets.append(preset)
        except Exception:
            pass

    return presets


def _parse_preset(data: dict[str, Any]) -> BenchmarkPreset | None:
    try:
        model_data = data.get("model")
        model = None
        if model_data:
            model = ModelAsset(
                filename=model_data.get("filename", ""),
                size_gib=model_data.get("size_gib", 0.0),
                url=model_data.get("url", ""),
                sha256=model_data.get("sha256", ""),
                license=model_data.get("license", "open"),
            )
        return BenchmarkPreset(
            id=data["id"],
            label=data["label"],
            category=data.get("category", "ml"),
            family=data.get("family", "llama_cpp"),
            description=data.get("description", ""),
            model=model,
            executable=data.get("executable", "llama-bench"),
            args=data.get("args", []),
            expected_vram_gib=data.get("expected_vram_gib", 0.0),
            repo_compatible=data.get("repo_compatible", True),
            tags=data.get("tags", []),
        )
    except (KeyError, TypeError):
        return None
