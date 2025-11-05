"""Utility functions for loading a local language model defined in connect_llm."""

from __future__ import annotations

import functools
import logging
import os
from pathlib import Path
from typing import Any, Dict, Tuple

from poseidon.utils.path_utils import resolve_config_path

if os.getenv("POSEIDON_DISABLE_LLM") == "1":  # pragma: no cover - used in tests
    def get_llm(force_new: bool = False):
        raise RuntimeError("Local LLM disabled via POSEIDON_DISABLE_LLM")

    __all__ = ["get_llm"]
else:  # pragma: no cover - requires langchain runtime deps
    import shlex
    import shutil
    import subprocess
    from typing import Mapping, Optional, Sequence

    import yaml
    from langchain_core.language_models import BaseLanguageModel, LLM
    from pydantic import Field

    LOGGER = logging.getLogger(__name__)


    class RemoteOllamaLLM(LLM):
        """LangChain-compatible wrapper that proxies prompts to a remote Ollama host via OpenSSH."""

        host: str = Field(..., description="SSH host name for the remote LLM server.")
        username: str = Field(..., description="SSH username.")
        password: str = Field(..., repr=False, description="SSH password.")
        command: str = Field(default="ollama run llama2", description="Command executed on the remote host.")
        port: int = Field(default=22, description="SSH port.")
        ip: Optional[str] = Field(default=None, description="Optional fallback IP address.")
        timeout: int = Field(default=180, description="Command timeout in seconds.")
        accept_unknown_hosts: bool = Field(default=True, description="Automatically add host keys if needed.")
        ssh_binary: str = Field(default="ssh", description="Path to OpenSSH binary.")
        ssh_options: Sequence[str] = Field(default_factory=tuple, description="Additional ssh CLI options.")

        @property
        def _llm_type(self) -> str:
            return "remote_ollama"

        @property
        def _identifying_params(self) -> Mapping[str, Any]:
            return {
                "host": self.host,
                "port": self.port,
                "command": self.command,
                "ssh_binary": self.ssh_binary,
            }

        def _call(self, prompt: str, stop: Optional[list[str]] = None, **kwargs: Any) -> str:
            response = self._execute_remote(prompt)
            if stop:
                for token in stop:
                    if token and token in response:
                        response = response.split(token)[0]
            return response.strip()

        def _execute_remote(self, prompt: str) -> str:
            ssh_command = self._build_ssh_command()
            stdin_input = prompt if prompt.endswith("\n") else prompt + "\n"

            LOGGER.debug("Executing remote LLM via command: %s", " ".join(shlex.quote(part) for part in ssh_command))
            process = subprocess.Popen(
                ssh_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            try:
                stdout, stderr = process.communicate(stdin_input, timeout=self.timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                raise RuntimeError("Remote LLM invocation timed out after "
                                   f"{self.timeout} seconds.") from None

            if process.returncode != 0:
                message = stderr.strip() or f"Remote command exited with status {process.returncode}"
                raise RuntimeError(f"Remote LLM invocation failed: {message}")

            return stdout

        def _build_ssh_command(self) -> list[str]:
            target_host = self.host or self.ip
            login = f"{self.username}@{target_host}"
            base_cmd: list[str] = []

            ssh_binary = self.ssh_binary or "ssh"
            ssh_parts = [ssh_binary, "-p", str(self.port)]

            if self.accept_unknown_hosts:
                ssh_parts.extend(
                    ["-oStrictHostKeyChecking=no", "-oUserKnownHostsFile=/dev/null"]
                )

            ssh_parts.extend(self.ssh_options or [])

            if self.password:
                sshpass_binary = shutil.which("sshpass")
                if sshpass_binary:
                    base_cmd.extend([sshpass_binary, "-p", self.password])
                else:
                    raise RuntimeError(
                        "SSH password provided but 'sshpass' is not installed. "
                        "Install sshpass or configure key-based authentication."
                    )

            remote_command = self._parse_remote_command(self.command)

            ssh_parts.append(login)
            ssh_parts.extend(remote_command)

            base_cmd.extend(ssh_parts)
            return base_cmd

        @staticmethod
        def _parse_remote_command(command: str) -> list[str]:
            if not command:
                raise ValueError("Remote LLM configuration requires a non-empty command.")
            return shlex.split(command)


    CONFIG_PATH = resolve_config_path("connect_llm.yaml")

    def _load_config() -> Dict[str, Any]:
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}


    def _build_remote_llm(config: Dict[str, Any]) -> BaseLanguageModel:
        model_section = config.get("model") or {}
        remote_section = model_section.get("remote") or config.get("remote") or {}

        host = remote_section.get("host") or remote_section.get("hostname")
        ip = remote_section.get("ip")
        username = remote_section.get("user") or remote_section.get("username")
        if not host and not ip:
            raise ValueError("Remote LLM configuration requires 'host' or 'ip'.")
        if not username:
            raise ValueError("Remote LLM configuration requires a 'user' field.")

        password = None
        password_env = remote_section.get("password_env_var")
        if password_env:
            password = os.getenv(password_env)
        if not password:
            password = remote_section.get("password")
        if not password:
            env_hint = password_env or "POSEIDON_LLM_PASSWORD"
            raise ValueError(
                "Remote LLM password not configured. Set the environment variable "
                f"'{env_hint}' or provide 'password' in {CONFIG_PATH}."
            )

        command = remote_section.get("command", "ollama run llama2")
        port = int(remote_section.get("port", 22))
        timeout = int(remote_section.get("timeout_seconds", remote_section.get("timeout", 180)))
        accept_unknown = bool(remote_section.get("accept_unknown_hosts", True))
        ssh_binary = remote_section.get("ssh_binary", "ssh")
        ssh_options = remote_section.get("ssh_options") or []
        if isinstance(ssh_options, str):
            ssh_options = shlex.split(ssh_options)
        elif not isinstance(ssh_options, (list, tuple)):
            raise ValueError("remote.ssh_options must be a list, tuple, or string if provided.")

        LOGGER.info(
            "Configured remote Ollama host %s:%s with command '%s'",
            host or ip,
            port,
            command,
        )
        return RemoteOllamaLLM(
            host=host or ip,
            ip=ip,
            username=username,
            password=password,
            command=command,
            port=port,
            timeout=timeout,
            accept_unknown_hosts=accept_unknown,
            ssh_binary=ssh_binary,
            ssh_options=tuple(ssh_options),
        )

    def _build_ollama_llm(config: Dict[str, Any]) -> BaseLanguageModel:
        try:
            from langchain_community.llms import Ollama
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "The 'langchain-community' package is required when using the Ollama provider."
            ) from exc

        model_section = config.get("model") or {}
        inference_section = config.get("inference") or {}

        base_url = model_section.get("base_url")
        if not base_url:
            host = os.getenv("POSEIDON_LLM_HOST", "127.0.0.1")
            port = os.getenv("POSEIDON_LLM_PORT", "11434")
            base_url = f"http://{host}:{port}"

        model_name = (
            model_section.get("model")
            or model_section.get("name")
            or os.getenv("POSEIDON_LLM_MODEL_NAME", "llama3")
        )

        llm_kwargs: Dict[str, Any] = {}
        for key in (
            "temperature",
            "top_p",
            "top_k",
            "mirostat",
            "mirostat_eta",
            "mirostat_tau",
            "num_ctx",
            "num_gpu",
            "num_thread",
            "num_predict",
            "repeat_last_n",
            "repeat_penalty",
            "tfs_z",
        ):
            value = inference_section.get(key)
            if value is not None:
                llm_kwargs[key] = value

        if inference_section.get("stop"):
            llm_kwargs["stop"] = inference_section["stop"]

        for key in ("system", "format", "template", "keep_alive", "timeout", "headers", "auth"):
            value = model_section.get(key)
            if value is not None:
                llm_kwargs[key] = value

        LOGGER.info("Configured local Ollama model '%s' via %s", model_name, base_url)
        return Ollama(base_url=base_url, model=model_name, **llm_kwargs)


    def _resolve_quantization_kwargs(model_section: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
        """Translate config quantization hints into model kwargs."""
        quantization = str(model_section.get("quantization", "")).lower().strip()
        if not quantization or quantization == "none":
            return {}, "none"

        if quantization not in {"4bit", "8bit"}:
            raise ValueError(
                f"Unsupported quantization setting '{quantization}' in {CONFIG_PATH}"
            )

        device_map = str(model_section.get("device_map", "auto")).lower()
        if device_map == "cpu":
            LOGGER.warning(
                "Quantization set to %s but device_map=cpu. Falling back to full precision.",
                quantization,
            )
            return {}, quantization

        try:
            import bitsandbytes  # noqa: F401
        except ImportError as exc:  # pragma: no cover - runtime environment check
            raise RuntimeError(
                "Quantized loading requires the 'bitsandbytes' package. Install it or set quantization to 'none'."
            ) from exc

        return {
            "load_in_4bit": quantization == "4bit",
            "load_in_8bit": quantization == "8bit",
        }, quantization


    def _load_local_llama_cpp(model_path: Path, config: Dict[str, Any]) -> BaseLanguageModel:
        from langchain_community.llms import LlamaCpp  # late import to avoid heavy deps

        model_section = config.get("model", {})
        inference_section = config.get("inference", {})
        n_ctx = int(model_section.get("max_seq_length", 1024))
        LOGGER.info("Loading LlamaCpp model from %s", model_path)
        return LlamaCpp(
            model_path=str(model_path),
            n_ctx=n_ctx,
            temperature=float(inference_section.get("temperature", 0.0)),
            n_batch=int(inference_section.get("batch_size", 1)),
            max_tokens=int(inference_section.get("max_tokens", 256)),
        )


    def _load_local_hf_pipeline(model_path: Path, config: Dict[str, Any]) -> BaseLanguageModel:
        import torch
        from langchain_community.llms.huggingface_pipeline import HuggingFacePipeline
        from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

        model_section = config.get("model", {})
        inference_section = config.get("inference", {})

        dtype_str = model_section.get("dtype", "float32")
        torch_dtype = getattr(torch, dtype_str, torch.float32)
        device_map = model_section.get("device_map", "auto")
        quant_kwargs, quantization = _resolve_quantization_kwargs(model_section)

        LOGGER.info(
            "Loading local HF model from %s with dtype=%s, device_map=%s, quantization=%s",
            model_path,
            dtype_str,
            device_map,
            quantization,
        )
        model = AutoModelForCausalLM.from_pretrained(
            str(model_path),
            torch_dtype=torch_dtype,
            device_map=device_map,
            trust_remote_code=bool(model_section.get("trust_remote_code", False)),
            **quant_kwargs,
        )
        tokenizer = AutoTokenizer.from_pretrained(str(model_path))

        text_pipeline = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
            max_new_tokens=int(inference_section.get("max_tokens", 256)),
            temperature=float(inference_section.get("temperature", 0.0)),
            pad_token_id=tokenizer.eos_token_id,
            do_sample=float(inference_section.get("temperature", 0.0)) > 0,
        )
        return HuggingFacePipeline(pipeline=text_pipeline)


    @functools.lru_cache(maxsize=1)
    def _load_llm() -> BaseLanguageModel:
        config = _load_config()
        model_section = config.get("model") or {}
        provider = str(model_section.get("provider", "local")).lower()

        if provider in {"remote", "remote_ollama", "ollama_remote"}:
            return _build_remote_llm(config)
        if provider in {"ollama", "local_ollama", "ollama_local"}:
            return _build_ollama_llm(config)

        model_path = Path(model_section.get("path", "")).expanduser()
        if not model_path.exists():
            raise FileNotFoundError(
                f"Local model path '{model_path}' does not exist; update {CONFIG_PATH}"
            )

        preferred_loader = (model_section.get("loader") or "").lower()
        if preferred_loader and preferred_loader not in {"llama_cpp", "hf", "auto"}:
            raise ValueError("model.loader must be one of 'llama_cpp', 'hf', or 'auto'")

        if preferred_loader == "llama_cpp" or model_path.suffix == ".gguf":
            return _load_local_llama_cpp(model_path, config)

        if preferred_loader == "hf" or model_path.is_dir():
            return _load_local_hf_pipeline(model_path, config)

        raise ValueError(
            f"Unable to determine loader for model path '{model_path}'. "
            f"Set model.loader explicitly in {CONFIG_PATH}."
        )


    def get_llm(force_new: bool = False) -> BaseLanguageModel:
        """Return a cached language model instance (remote or local)."""
        if force_new:
            _load_llm.cache_clear()
        return _load_llm()


    __all__ = ["get_llm"]
