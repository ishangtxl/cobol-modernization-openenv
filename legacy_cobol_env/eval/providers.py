"""Provider adapters for model-driven evaluation rollouts."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol


class TextProvider(Protocol):
    name: str

    def generate(self, prompt: str) -> str:
        """Return provider text for one migration prompt."""


@dataclass(frozen=True)
class StaticResponseProvider:
    name: str
    response: str

    def generate(self, prompt: str) -> str:
        return self.response


@dataclass
class SequenceResponseProvider:
    name: str
    responses: list[str]
    index: int = 0

    def generate(self, prompt: str) -> str:
        if self.index >= len(self.responses):
            return self.responses[-1]
        response = self.responses[self.index]
        self.index += 1
        return response


@dataclass(frozen=True)
class AzureOpenAIProvider:
    endpoint: str
    api_key: str
    deployment: str
    api_version: str = "2024-02-15-preview"
    name: str = "azure-openai"
    timeout_s: float = 60.0

    def generate(self, prompt: str) -> str:
        url = (
            f"{self.endpoint.rstrip('/')}/openai/deployments/{self.deployment}"
            f"/chat/completions?api-version={self.api_version}"
        )
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": "Return only JSON with a single code field containing a Python migrate function.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        }
        data = _post_json(
            url,
            payload,
            headers={"api-key": self.api_key, "Content-Type": "application/json"},
            timeout_s=self.timeout_s,
        )
        return data["choices"][0]["message"]["content"]


@dataclass(frozen=True)
class HuggingFaceEndpointProvider:
    endpoint: str
    token: str
    name: str = "hf-endpoint"
    timeout_s: float = 60.0

    def generate(self, prompt: str) -> str:
        data = _post_json(
            self.endpoint,
            {"inputs": prompt, "parameters": {"temperature": 0.0, "max_new_tokens": 1800}},
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
            timeout_s=self.timeout_s,
        )
        if isinstance(data, list) and data and "generated_text" in data[0]:
            return data[0]["generated_text"]
        if isinstance(data, dict) and "generated_text" in data:
            return data["generated_text"]
        if isinstance(data, dict) and "choices" in data:
            return data["choices"][0]["message"]["content"]
        raise ValueError("HF endpoint response did not contain generated text")


@dataclass
class LocalTransformersProvider:
    model_path: str
    base_model_path: str | None = None
    name: str = "local-transformers"
    max_new_tokens: int = 1800
    load_in_4bit: bool = True
    _model: object | None = None
    _tokenizer: object | None = None

    def generate(self, prompt: str) -> str:
        tokenizer, model = self._load()
        prompt_text = self._format_prompt(tokenizer, prompt)
        inputs = tokenizer(prompt_text, return_tensors="pt")
        inputs = inputs.to(model.device) if hasattr(inputs, "to") else inputs
        output_ids = model.generate(
            **inputs,
            max_new_tokens=self.max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
        prompt_length = inputs["input_ids"].shape[-1]
        generated = output_ids[0][prompt_length:]
        return tokenizer.decode(generated, skip_special_tokens=True)

    def _format_prompt(self, tokenizer: object, prompt: str) -> str:
        messages = [
            {
                "role": "system",
                "content": "Return only JSON with a single code field containing a Python migrate function.",
            },
            {"role": "user", "content": prompt},
        ]
        if hasattr(tokenizer, "apply_chat_template"):
            return tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        return prompt

    def _load(self) -> tuple[object, object]:
        if self._model is not None and self._tokenizer is not None:
            return self._tokenizer, self._model
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("install training/requirements-gpu.txt to use local-transformers") from exc
        quantization_config = self._quantization_config()
        adapter_base = self._adapter_base_model_path()
        if adapter_base:
            try:
                from peft import PeftModel
            except ImportError as exc:
                raise RuntimeError("install peft from training/requirements-gpu.txt to load LoRA adapters") from exc
            tokenizer = AutoTokenizer.from_pretrained(self.model_path, trust_remote_code=True)
            model = AutoModelForCausalLM.from_pretrained(
                adapter_base,
                device_map="auto",
                quantization_config=quantization_config,
                trust_remote_code=True,
            )
            model = PeftModel.from_pretrained(model, self.model_path)
        else:
            tokenizer = AutoTokenizer.from_pretrained(self.model_path, trust_remote_code=True)
            model = AutoModelForCausalLM.from_pretrained(
                self.model_path,
                device_map="auto",
                quantization_config=quantization_config,
                trust_remote_code=True,
            )
        self._tokenizer = tokenizer
        self._model = model
        return tokenizer, model

    def _adapter_base_model_path(self) -> str | None:
        if self.base_model_path:
            return self.base_model_path
        config_path = Path(self.model_path) / "adapter_config.json"
        if not config_path.exists():
            return None
        data = json.loads(config_path.read_text(encoding="utf-8"))
        return data.get("base_model_name_or_path")

    def _quantization_config(self) -> object | None:
        if not self.load_in_4bit:
            return None
        try:
            from transformers import BitsAndBytesConfig
        except ImportError as exc:
            raise RuntimeError("install bitsandbytes and transformers from training/requirements-gpu.txt") from exc
        return BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype="bfloat16",
        )


def create_provider(kind: str, env: Mapping[str, str]) -> TextProvider:
    if kind == "azure-openai":
        required = ["AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_DEPLOYMENT"]
        missing = [key for key in required if not env.get(key)]
        if missing:
            raise ValueError(f"missing Azure OpenAI configuration: {', '.join(missing)}")
        return AzureOpenAIProvider(
            endpoint=env["AZURE_OPENAI_ENDPOINT"],
            api_key=env["AZURE_OPENAI_API_KEY"],
            deployment=env["AZURE_OPENAI_DEPLOYMENT"],
            api_version=env.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
        )

    if kind == "hf-endpoint":
        required = ["HF_INFERENCE_ENDPOINT", "HF_TOKEN"]
        missing = [key for key in required if not env.get(key)]
        if missing:
            raise ValueError(f"missing Hugging Face endpoint configuration: {', '.join(missing)}")
        return HuggingFaceEndpointProvider(
            endpoint=env["HF_INFERENCE_ENDPOINT"],
            token=env["HF_TOKEN"],
        )

    if kind == "static":
        return StaticResponseProvider("static", env.get("STATIC_RESPONSE", '{"code": "def migrate(input_record: str) -> str:\\n    return input_record\\n"}'))

    if kind == "local-transformers":
        if not env.get("LOCAL_MODEL_PATH"):
            raise ValueError("missing local Transformers configuration: LOCAL_MODEL_PATH")
        return LocalTransformersProvider(
            model_path=env["LOCAL_MODEL_PATH"],
            base_model_path=env.get("LOCAL_BASE_MODEL_PATH"),
            max_new_tokens=int(env.get("LOCAL_MAX_NEW_TOKENS", "1800")),
            load_in_4bit=env.get("LOCAL_LOAD_IN_4BIT", "1").lower() not in {"0", "false", "no"},
        )

    raise ValueError(f"unknown provider: {kind}")


def _post_json(url: str, payload: object, headers: dict[str, str], timeout_s: float) -> object:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"provider HTTP {exc.code}: {body}") from exc
