from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ReasoningSource(_message.Message):
    __slots__ = ("doc_id", "node_ids")
    DOC_ID_FIELD_NUMBER: _ClassVar[int]
    NODE_IDS_FIELD_NUMBER: _ClassVar[int]
    doc_id: str
    node_ids: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, doc_id: _Optional[str] = ..., node_ids: _Optional[_Iterable[str]] = ...) -> None: ...

class ChatRequest(_message.Message):
    __slots__ = ("message", "user_id", "thread_id")
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    THREAD_ID_FIELD_NUMBER: _ClassVar[int]
    message: str
    user_id: str
    thread_id: str
    def __init__(self, message: _Optional[str] = ..., user_id: _Optional[str] = ..., thread_id: _Optional[str] = ...) -> None: ...

class ChatResponse(_message.Message):
    __slots__ = ("content", "sources", "tokens_used", "latency_ms")
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    SOURCES_FIELD_NUMBER: _ClassVar[int]
    TOKENS_USED_FIELD_NUMBER: _ClassVar[int]
    LATENCY_MS_FIELD_NUMBER: _ClassVar[int]
    content: str
    sources: _containers.RepeatedCompositeFieldContainer[ReasoningSource]
    tokens_used: int
    latency_ms: int
    def __init__(self, content: _Optional[str] = ..., sources: _Optional[_Iterable[_Union[ReasoningSource, _Mapping]]] = ..., tokens_used: _Optional[int] = ..., latency_ms: _Optional[int] = ...) -> None: ...
