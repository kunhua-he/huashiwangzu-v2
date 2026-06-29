from .runtime_policy import RuntimePolicy
from .stream_emitter import StreamEmitter
from .task_sink import RuntimeTaskSink

__all__ = [
    "RuntimePolicy",
    "StreamEmitter",
    "RuntimeTaskSink",
    "ToolLoopRuntime",
    "ConversationRuntime",
    "UnderstandingLoopOrchestrator",
]


def __getattr__(name: str):
    if name == "ToolLoopRuntime":
        from .tool_loop_runtime import ToolLoopRuntime
        return ToolLoopRuntime
    if name == "ConversationRuntime":
        from .conversation_runtime import ConversationRuntime
        return ConversationRuntime
    if name == "UnderstandingLoopOrchestrator":
        from .understanding_loop import UnderstandingLoopOrchestrator
        return UnderstandingLoopOrchestrator
    raise AttributeError(name)
