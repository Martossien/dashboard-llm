"""
GPU backend factory — auto-detection NVIDIA ou fallback.
"""

import logging

logger = logging.getLogger("dashboard-llm.gpu")


def get_gpu_backend():
    """Auto-detection du backend GPU disponible.

    Ordre: NVIDIA → NoGPU fallback.
    """
    try:
        from llm_dashboard.monitors.gpu.nvidia import NvidiaBackend
        backend = NvidiaBackend()
        if backend.initialize():
            return backend
    except Exception as e:
        logger.debug("NVIDIA backend unavailable: %s", e)

    from llm_dashboard.monitors.gpu.nogpu import NoGPUBackend
    logger.info("GPU backend: none (NoGPU)")
    return NoGPUBackend()
