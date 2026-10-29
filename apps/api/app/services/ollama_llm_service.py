"""
services/ollama_llm_service.py — Service for interacting with local Ollama LLM.
"""

import json
import logging
from typing import Any, Optional

import httpx
from app.config import settings
from app.services.prompts import build_system_prompt as build_strict_prompt
from app.services.prompts import extract_prd_json

logger = logging.getLogger("app.api.ollama")

class OllamaLLMService:
    """
    Service for interacting with local Ollama LLM to facilitate
    actual chat-driven PRD generation.
    """

    def __init__(self):
        self.base_url = settings.ollama_base_url
        self.model = settings.ollama_model
        self.timeout = settings.ollama_timeout

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
    ):
        """
        Send a chat request to Ollama and yield the assistant tokens.
        """
        target_model = model or self.model
        url = f"{self.base_url}/api/chat"
        
        payload = {
            "model": target_model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": 0.3,
                "num_ctx": 8192,
            }
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                print(f"[DEBUG] Requesting Ollama: {url} with model {target_model}", flush=True)
                async with client.stream("POST", url, json=payload) as response:
                    print(f"[DEBUG] Ollama response status: {response.status_code}", flush=True)
                    response.raise_for_status()
                    print(f"[DEBUG] Ollama stream started", flush=True)
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        chunk = json.loads(line)
                        if "message" in chunk:
                            msg = chunk["message"]
                            if "content" in msg and msg["content"]:
                                yield {"content": msg["content"]}
                            if "thinking" in msg and msg["thinking"]:
                                yield {"thinking": msg["thinking"]}
                        if chunk.get("done"):
                            break
            except httpx.ConnectError as e:
                logger.error(f"Failed to connect to Ollama (Connection Refused): {str(e)}")
                raise
            except httpx.TimeoutException as e:
                logger.error(f"Ollama request timed out after {self.timeout}s: {str(e)}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error in Ollama stream: {type(e).__name__}: {str(e)}")
                raise

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
    ) -> str:
        """
        Send a chat request to Ollama and return the assistant message content.
        
        Parameters
        ----------
        messages : list[dict]
            List of message objects (role: user/assistant/system, content: string)
        model : str, optional
            Model name override.
        """
        target_model = model or self.model
        url = f"{self.base_url}/api/chat"
        
        payload = {
            "model": target_model,
            "messages": messages,
            "stream": False,  # Non-streaming for now
            "options": {
                "temperature": 0.3,  # Lower temperature for structured extraction
                "num_ctx": 8192,
            }
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("message", {}).get("content", "")
            except httpx.HTTPStatusError as e:
                logger.error(f"Ollama API error ({e.response.status_code}): {e.response.text}")
                raise
            except httpx.ConnectError as e:
                logger.error(f"Failed to connect to Ollama (Connection Refused): {str(e)}. Is Ollama running on the host?")
                raise
            except httpx.TimeoutException as e:
                logger.error(f"Ollama request timed out after {self.timeout}s: {str(e)}. The model might be too slow to load.")
                raise
            except Exception as e:
                logger.error(f"Unexpected error connecting to Ollama: {type(e).__name__}: {str(e)}")
                raise

    def extract_prd_json(self, text: str) -> dict[str, Any]:
        """Extract the PRD JSON object from the response (see prompts module)."""
        return extract_prd_json(text)

    def build_system_prompt(self, current_prd_draft: Optional[dict[str, Any]] = None) -> str:
        """Build the strict PRD system prompt for the current draft."""
        return build_strict_prompt(current_prd_draft or {"schema_version": "0.1.0"})
