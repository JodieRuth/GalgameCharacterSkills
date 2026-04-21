"""任务请求模型模块，定义 summarize、skills 与角色卡生成的输入契约。"""

from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar


@dataclass
class BaseTaskRequest:
    CHECKPOINT_FIELDS: ClassVar[tuple[str, ...]] = ()

    def apply_checkpoint(self, input_params):
        for field_name in self.CHECKPOINT_FIELDS:
            if field_name in input_params:
                setattr(self, field_name, input_params[field_name])
        return self

    def to_checkpoint_input(self):
        return {field_name: getattr(self, field_name) for field_name in self.CHECKPOINT_FIELDS}


@dataclass
class SummarizeRequest(BaseTaskRequest):
    CHECKPOINT_FIELDS: ClassVar[tuple[str, ...]] = (
        "role_name",
        "instruction",
        "output_language",
        "mode",
        "vndb_data",
        "slice_size_k",
        "file_paths",
        "concurrency",
    )

    role_name: str = ""
    instruction: str = ""
    concurrency: int = 1
    mode: str = "skills"
    resume_checkpoint_id: str | None = None
    output_language: str = ""
    vndb_data: Any = None
    slice_size_k: int = 50
    file_paths: list[str] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload, clean_vndb_data: Callable[[Any], Any], extract_file_paths: Callable[[dict], list[str]]):
        return cls(
            role_name=payload.get("role_name", ""),
            instruction=payload.get("instruction", ""),
            concurrency=payload.get("concurrency", 1),
            mode=payload.get("mode", "skills"),
            resume_checkpoint_id=payload.get("resume_checkpoint_id"),
            output_language=payload.get("output_language", ""),
            vndb_data=clean_vndb_data(payload.get("vndb_data")),
            slice_size_k=payload.get("slice_size_k", 50),
            file_paths=extract_file_paths(payload),
        )


@dataclass
class GenerateSkillsRequest(BaseTaskRequest):
    CHECKPOINT_FIELDS: ClassVar[tuple[str, ...]] = (
        "role_name",
        "vndb_data",
        "output_language",
        "compression_mode",
        "force_no_compression",
    )

    role_name: str = ""
    vndb_data: Any = None
    output_language: str = ""
    compression_mode: str = "original"
    force_no_compression: bool = False
    resume_checkpoint_id: str | None = None
    model_name: str = ""

    @classmethod
    def from_payload(cls, payload, clean_vndb_data: Callable[[Any], Any]):
        return cls(
            role_name=payload.get("role_name", ""),
            vndb_data=clean_vndb_data(payload.get("vndb_data")),
            output_language=payload.get("output_language", ""),
            compression_mode=payload.get("compression_mode", "original"),
            force_no_compression=payload.get("force_no_compression", False),
            resume_checkpoint_id=payload.get("resume_checkpoint_id"),
            model_name=payload.get("modelname", ""),
        )


@dataclass
class GenerateCharacterCardRequest(BaseTaskRequest):
    CHECKPOINT_FIELDS: ClassVar[tuple[str, ...]] = (
        "role_name",
        "creator",
        "vndb_data",
        "vndb_data_raw",
        "output_language",
        "compression_mode",
        "force_no_compression",
    )

    role_name: str = ""
    creator: str = ""
    vndb_data_raw: Any = None
    vndb_data: Any = None
    output_language: str = ""
    compression_mode: str = "original"
    force_no_compression: bool = False
    resume_checkpoint_id: str | None = None
    model_name: str = ""

    @classmethod
    def from_payload(cls, payload, clean_vndb_data: Callable[[Any], Any]):
        vndb_data_raw = payload.get("vndb_data")
        return cls(
            role_name=payload.get("role_name", ""),
            creator=payload.get("creator", ""),
            vndb_data_raw=vndb_data_raw,
            vndb_data=clean_vndb_data(vndb_data_raw),
            output_language=payload.get("output_language", ""),
            compression_mode=payload.get("compression_mode", "original"),
            force_no_compression=payload.get("force_no_compression", False),
            resume_checkpoint_id=payload.get("resume_checkpoint_id"),
            model_name=payload.get("modelname", ""),
        )
