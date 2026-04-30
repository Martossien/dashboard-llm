"""
NVIDIA GPU backend — utilise pynvml et CommandRunner.
"""

import logging
from llm_dashboard.services.commands import CommandRunner
from llm_dashboard.monitors.gpu.base import AbstractGPUBackend, GPUDevice

logger = logging.getLogger("dashboard-llm.gpu.nvidia")


class NvidiaBackend(AbstractGPUBackend):
    """Backend NVIDIA via pynvml + CommandRunner (nvidia-smi)."""

    def __init__(self, runner=None):
        self._initialized = False
        self._mode = None  # 'pynvml' | 'smi'
        self._runner = runner or CommandRunner()

    def initialize(self) -> bool:
        try:
            import pynvml
            pynvml.nvmlInit()
            self._pynvml = pynvml
            self._initialized = True
            self._mode = 'pynvml'
            logger.info("GPU backend: NVIDIA (pynvml)")
            return True
        except Exception as e:
            logger.warning("Failed to initialize NVML: %s", e)

        result = self._runner.nvidia_smi_query_gpu_full(timeout=5)
        if result.success and result.stdout.strip():
            self._initialized = True
            self._mode = 'smi'
            logger.info("GPU backend: NVIDIA (nvidia-smi, pynvml unavailable)")
            return True

        return False

    @property
    def vendor_name(self) -> str:
        return "nvidia"

    def get_devices(self) -> list[GPUDevice]:
        if not self._initialized:
            return []
        if self._mode == 'smi':
            return self._get_devices_via_smi()
        return self._get_devices_via_pynvml()

    def _get_devices_via_smi(self) -> list[GPUDevice]:
        result = self._runner.nvidia_smi_query_gpu_full(timeout=10)
        if not result.success or not result.stdout.strip():
            return []
        devices = []
        for line in result.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 10:
                continue
            try:
                def _f(val):
                    return float(val) if val not in ('', '[N/A]', 'N/A') else None
                devices.append(GPUDevice(
                    index=int(parts[0]), name=parts[1], vendor="nvidia",
                    memory_used_mib=float(parts[2]),
                    memory_free_mib=float(parts[3]),
                    memory_total_mib=float(parts[4]),
                    temperature_c=_f(parts[5]),
                    fan_speed_pct=_f(parts[6]),
                    utilization_gpu_pct=_f(parts[7]),
                    power_draw_w=_f(parts[8]),
                    power_limit_w=_f(parts[9]),
                ))
            except (ValueError, IndexError):
                continue
        return devices

    def _get_devices_via_pynvml(self) -> list[GPUDevice]:
        devices = []
        p = self._pynvml
        count = p.nvmlDeviceGetCount()
        for i in range(count):
            handle = p.nvmlDeviceGetHandleByIndex(i)
            name = p.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8")

            mem = p.nvmlDeviceGetMemoryInfo(handle)
            util = p.nvmlDeviceGetUtilizationRates(handle)

            temp = self._safe(p.nvmlDeviceGetTemperature, handle, p.NVML_TEMPERATURE_GPU)
            if temp is not None:
                temp = float(temp)
            fan = self._safe(p.nvmlDeviceGetFanSpeed, handle)
            if fan is not None:
                fan = float(fan)
            power = self._safe(p.nvmlDeviceGetPowerUsage, handle)
            if power is not None:
                power = power / 1000.0
            power_limit = self._safe(p.nvmlDeviceGetPowerManagementLimit, handle)
            if power_limit is not None:
                power_limit = int(power_limit) / 1000.0

            # Nouvelles metriques Lot 22
            _nvml_temp_memory = getattr(p, 'NVML_TEMPERATURE_MEMORY', 1)
            vram_temp = self._safe(p.nvmlDeviceGetTemperature, handle, _nvml_temp_memory)
            sm_clock = self._safe(p.nvmlDeviceGetClockInfo, handle, p.NVML_CLOCK_SM)
            mem_clock = self._safe(p.nvmlDeviceGetClockInfo, handle, p.NVML_CLOCK_MEM)
            throttle_reasons = self._safe(p.nvmlDeviceGetCurrentClocksThrottleReasons, handle)
            if throttle_reasons is None:
                is_throttled = None
            else:
                is_throttled = throttle_reasons != p.nvmlClocksThrottleReasonNone
            enc_result = self._safe(p.nvmlDeviceGetEncoderUtilization, handle)
            dec_result = self._safe(p.nvmlDeviceGetDecoderUtilization, handle)
            encoder_util = enc_result[0] if isinstance(enc_result, (tuple, list)) else enc_result
            decoder_util = dec_result[0] if isinstance(dec_result, (tuple, list)) else dec_result

            devices.append(GPUDevice(
                index=i, name=name, vendor="nvidia",
                memory_total_mib=mem.total / (1024**2),
                memory_used_mib=mem.used / (1024**2),
                memory_free_mib=mem.free / (1024**2),
                temperature_c=temp,
                fan_speed_pct=fan,
                utilization_gpu_pct=util.gpu,
                utilization_memory_pct=util.memory,
                power_draw_w=power,
                power_limit_w=power_limit,
                vram_temp_c=float(vram_temp) if vram_temp is not None else None,
                sm_clock_mhz=int(sm_clock) if sm_clock is not None else None,
                mem_clock_mhz=int(mem_clock) if mem_clock is not None else None,
                is_throttled=is_throttled,
                encoder_util_pct=int(encoder_util) if encoder_util is not None else None,
                decoder_util_pct=int(decoder_util) if decoder_util is not None else None,
            ))
        return devices

    def _safe(self, fn, *args, default=None):
        """Appel pynvml protege — retourne default si indisponible."""
        try:
            return fn(*args)
        except Exception:
            return default

    def shutdown(self):
        if self._initialized:
            try:
                self._pynvml.nvmlShutdown()
            except Exception:
                pass

    def get_gpu_processes(self) -> list[dict]:
        if not self._initialized:
            return []
        if self._mode == "pynvml":
            return self._get_gpu_processes_via_pynvml()
        return self._get_gpu_processes_via_smi()

    def _get_gpu_processes_via_pynvml(self) -> list[dict]:
        """Collecte les processus GPU via pynvml avec enrichissement psutil."""
        from llm_dashboard.monitors.gpu.processes import GPUProcess, guess_gpu_process_service

        processes = []
        p = self._pynvml
        try:
            count = p.nvmlDeviceGetCount()
        except Exception as exc:
            logger.warning("Failed to get GPU count: %s", exc)
            return []

        for i in range(count):
            try:
                handle = p.nvmlDeviceGetHandleByIndex(i)
                gpu_uuid = self._safe(p.nvmlDeviceGetUUID, handle)
            except Exception:
                continue

            for proc in self._safe(p.nvmlDeviceGetComputeRunningProcesses, handle, default=[]) or []:
                pid = getattr(proc, 'pid', 0)
                vram_bytes = getattr(proc, 'usedGpuMemory', None)
                if vram_bytes is None:
                    vram_bytes = 0
                used_vram = vram_bytes / (1024 * 1024) if vram_bytes else 0.0

                proc_name, username, cmd = self._enrich_process(pid)
                service = guess_gpu_process_service(proc_name, cmd)

                processes.append({
                    "pid": pid,
                    "gpu_index": i,
                    "process_name": proc_name,
                    "used_vram_mib": used_vram,
                    "username": username,
                    "command": cmd,
                    "service_guess": service,
                    "backend": "nvidia",
                    "gpu_uuid": gpu_uuid,
                })

        return processes

    def _get_gpu_processes_via_smi(self) -> list[dict]:
        """Collecte les processus GPU via nvidia-smi avec enrichissement psutil."""
        from llm_dashboard.monitors.gpu.processes import guess_gpu_process_service

        result = self._runner.nvidia_smi_query_compute_apps(timeout=10)
        if not result.success:
            return []
        processes = []
        for line in result.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 3:
                continue
            try:
                pid = int(parts[0])
                smi_name = parts[1]
                vram_mib = float(parts[2])
            except (ValueError, IndexError):
                continue

            proc_name, username, cmd = self._enrich_process(pid)
            service = guess_gpu_process_service(proc_name or smi_name, cmd)

            processes.append({
                "pid": pid,
                "gpu_index": None,
                "process_name": proc_name or smi_name,
                "used_vram_mib": vram_mib,
                "username": username,
                "command": cmd,
                "service_guess": service,
                "backend": "nvidia",
                "gpu_uuid": None,
            })

        return processes

    def _enrich_process(self, pid: int) -> tuple:
        """Enrichit un PID avec psutil : process_name, username, command.

        Returns:
            tuple (process_name: str, username: str|None, command: str|None)
        """
        proc_name = f"pid-{pid}"
        username = None
        command = None
        try:
            import psutil as _ps
            proc = _ps.Process(pid)
            proc_name = proc.name()
            try:
                username = proc.username()
            except Exception:
                pass
            try:
                cmdline = proc.cmdline()
                command = " ".join(cmdline)[:4096] if cmdline else None
            except Exception:
                pass
        except Exception:
            pass
        return proc_name, username, command
