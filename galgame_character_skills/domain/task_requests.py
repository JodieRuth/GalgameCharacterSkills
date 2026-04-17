from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class SummarizeRequest:
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

    def apply_checkpoint(self, input_params):
        self.role_name = input_params.get("role_name", self.role_name)
        self.instruction = input_params.get("instruction", self.instruction)
        self.concurrency = input_params.get("concurrency", self.concurrency)
        self.mode = input_params.get("mode", self.mode)
        self.output_language = input_params.get("output_language", self.output_language)
        self.vndb_data = input_params.get("vndb_data", self.vndb_data)
        self.slice_size_k = input_params.get("slice_size_k", self.slice_size_k)
        self.file_paths = input_params.get("file_paths", self.file_paths)
        return self

    def to_checkpoint_input(self):
        return {
            "role_name": self.role_name,
            "instruction": self.instruction,
            "output_language": self.output_language,
            "mode": self.mode,
            "vndb_data": self.vndb_data,
            "slice_size_k": self.slice_size_k,
            "file_paths": self.file_paths,
            "concurrency": self.concurrency,
        }


@dataclass
class GenerateSkillsRequest:
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

    def apply_checkpoint(self, input_params):
        self.role_name = input_params.get("role_name", self.role_name)
        self.vndb_data = input_params.get("vndb_data", self.vndb_data)
        self.output_language = input_params.get("output_language", self.output_language)
        self.compression_mode = input_params.get("compression_mode", self.compression_mode)
        self.force_no_compression = input_params.get("force_no_compression", self.force_no_compression)
        return self

    def to_checkpoint_input(self):
        return {
            "role_name": self.role_name,
            "vndb_data": self.vndb_data,
            "output_language": self.output_language,
            "compression_mode": self.compression_mode,
            "force_no_compression": self.force_no_compression,
        }


@dataclass
class GenerateCharacterCardRequest:
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

    def apply_checkpoint(self, input_params):
        self.role_name = input_params.get("role_name", self.role_name)
        self.creator = input_params.get("creator", self.creator)
        self.vndb_data = input_params.get("vndb_data", self.vndb_data)
        self.vndb_data_raw = input_params.get("vndb_data_raw", self.vndb_data_raw)
        self.output_language = input_params.get("output_language", self.output_language)
        self.compression_mode = input_params.get("compression_mode", self.compression_mode)
        self.force_no_compression = input_params.get("force_no_compression", self.force_no_compression)
        return self

    def to_checkpoint_input(self):
        return {
            "role_name": self.role_name,
            "creator": self.creator,
            "vndb_data": self.vndb_data,
            "vndb_data_raw": self.vndb_data_raw,
            "output_language": self.output_language,
            "compression_mode": self.compression_mode,
            "force_no_compression": self.force_no_compression,
        }
