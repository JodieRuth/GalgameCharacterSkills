"""任务请求模型模块，定义 summarize、skills 与角色卡生成的输入契约。"""

from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar


def _read_model_name(payload: dict[str, Any]) -> str:
    """兼容读取模型名称字段，内部统一使用 model_name。"""
    return payload.get("model_name") or payload.get("modelname", "")


@dataclass
class BaseTaskRequest:
    CHECKPOINT_FIELDS: ClassVar[tuple[str, ...]] = ()

    def apply_checkpoint(self, input_params: dict[str, Any]) -> "BaseTaskRequest":
        """将 checkpoint 输入参数回填到请求对象。

        Args:
            input_params: checkpoint 中保存的输入参数。

        Returns:
            BaseTaskRequest: 当前请求对象。

        Raises:
            Exception: 字段回填失败时向上抛出。
        """
        for field_name in self.CHECKPOINT_FIELDS:
            if field_name in input_params:
                setattr(self, field_name, input_params[field_name])
        return self

    def to_checkpoint_input(self) -> dict[str, Any]:
        """导出可写入 checkpoint 的输入参数。

        Args:
            None

        Returns:
            dict[str, Any]: checkpoint 输入参数。

        Raises:
            Exception: 参数导出失败时向上抛出。
        """
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
    def from_payload(
        cls,
        payload: dict[str, Any],
        clean_vndb_data: Callable[[Any], Any],
        extract_file_paths: Callable[[dict[str, Any]], list[str]],
    ) -> "SummarizeRequest":
        """从请求载荷构造归纳请求。

        Args:
            payload: 原始请求数据。
            clean_vndb_data: VNDB 数据清洗函数。
            extract_file_paths: 文件路径提取函数。

        Returns:
            SummarizeRequest: 标准化后的归纳请求。

        Raises:
            Exception: 请求构造失败时向上抛出。
        """
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
    def from_payload(
        cls,
        payload: dict[str, Any],
        clean_vndb_data: Callable[[Any], Any],
    ) -> "GenerateSkillsRequest":
        """从请求载荷构造技能生成请求。

        Args:
            payload: 原始请求数据。
            clean_vndb_data: VNDB 数据清洗函数。

        Returns:
            GenerateSkillsRequest: 标准化后的技能生成请求。

        Raises:
            Exception: 请求构造失败时向上抛出。
        """
        return cls(
            role_name=payload.get("role_name", ""),
            vndb_data=clean_vndb_data(payload.get("vndb_data")),
            output_language=payload.get("output_language", ""),
            compression_mode=payload.get("compression_mode", "original"),
            force_no_compression=payload.get("force_no_compression", False),
            resume_checkpoint_id=payload.get("resume_checkpoint_id"),
            model_name=_read_model_name(payload),
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
    def from_payload(
        cls,
        payload: dict[str, Any],
        clean_vndb_data: Callable[[Any], Any],
    ) -> "GenerateCharacterCardRequest":
        """从请求载荷构造角色卡生成请求。

        Args:
            payload: 原始请求数据。
            clean_vndb_data: VNDB 数据清洗函数。

        Returns:
            GenerateCharacterCardRequest: 标准化后的角色卡生成请求。

        Raises:
            Exception: 请求构造失败时向上抛出。
        """
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
            model_name=_read_model_name(payload),
        )
