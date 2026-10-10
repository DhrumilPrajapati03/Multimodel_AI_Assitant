"""Small-server mode for ONNX Runtime (embeddings + Piper TTS), enabled by ONNX_THREADS.

By default ONNX Runtime starts one thread per CPU core it can see. On small cloud
plans (e.g. Render Free: 0.1 CPU on a 16-core host) those threads fight over a tiny
CPU quota and a single request can take a minute. ONNX_THREADS=1 avoids that.
Import this module before any ONNX model is loaded.
"""
import os

import onnxruntime

_threads = int(os.getenv("ONNX_THREADS", "0"))   # 0 = ONNX Runtime's default

if _threads > 0 and not getattr(onnxruntime.SessionOptions, "_capped", False):
    class _CappedSessionOptions(onnxruntime.SessionOptions):
        _capped = True

        def __init__(self):
            super().__init__()
            self.intra_op_num_threads = _threads
            self.inter_op_num_threads = 1
            # Return working memory after each run instead of keeping a growing arena:
            # ~120 MB less after indexing documents, which matters on a 512 MB plan.
            self.enable_cpu_mem_arena = False

    onnxruntime.SessionOptions = _CappedSessionOptions
