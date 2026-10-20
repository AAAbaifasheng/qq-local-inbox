from __future__ import annotations

API_PRESETS = {
    "Ollama": "http://127.0.0.1:11434/v1/chat/completions",
    "LM Studio": "http://127.0.0.1:1234/v1/chat/completions",
    "DeepSeek": "https://api.deepseek.com/v1/chat/completions",
}

API_PRESET_MODELS = {
    "DeepSeek": ("deepseek-flash", "deepseek-v4-pro"),
}
