"""OpenAI-compatible LLM client for transcript cleanup.

Works with: OpenAI, Ollama (http://host:11434/v1), LM Studio, Groq, any
OpenAI-compatible endpoint.
"""
import json
import urllib.request
import urllib.error


DEFAULT_SYSTEM_PROMPT = (
    "You are a transcription cleanup assistant. The user dictated text via "
    "speech-to-text and the result may have errors. Your job:\n"
    "- Fix punctuation, capitalization, and obvious word recognition errors.\n"
    "- Remove filler words (um, uh, like) only when they're clearly fillers.\n"
    "- Preserve meaning, tone, and intent. Do not add content or rephrase.\n"
    "- Output ONLY the cleaned text. No preamble, no explanations, no quotes."
)


class LLMClient:
    def __init__(self, base_url, api_key, model, system_prompt=None, timeout=20):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or ""
        self.model = model
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self.timeout = timeout

    def clean(self, text):
        if not text or not text.strip():
            return text
        url = f"{self.base_url}/chat/completions"
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": text},
            ],
            "temperature": 0.1,
            "max_tokens": max(200, len(text) * 2),
            "stream": False,
        }
        data = json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"LLM HTTP {e.code}: {e.read()[:200].decode('utf-8', 'replace')}")
        except Exception as e:
            raise RuntimeError(f"LLM error: {e}")
        try:
            out = payload["choices"][0]["message"]["content"].strip()
            # Strip surrounding quotes if model added them
            if out.startswith('"') and out.endswith('"') and len(out) > 1:
                out = out[1:-1]
            return out
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"LLM bad response: {e}")

    def ping(self):
        """Quick health check. Returns (ok, message)."""
        try:
            url = f"{self.base_url}/models"
            req = urllib.request.Request(url)
            if self.api_key:
                req.add_header("Authorization", f"Bearer {self.api_key}")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return True, f"OK ({resp.status})"
        except Exception as e:
            return False, str(e)
