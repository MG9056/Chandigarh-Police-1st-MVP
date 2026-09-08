"""
DarKnight AI — Backend Service Layer

Handles hosted LLM API interactions using the google-genai SDK with streaming,
session-derived user context, dynamic environment key resolution, and model fallbacks.
"""

import asyncio
import logging
import os
from typing import AsyncGenerator, Dict, List, Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types

from utils.ai_prompts import build_system_instruction

logger = logging.getLogger(__name__)


class AIService:
    """
    Service layer for DarKnight AI Copilot interactions.

    Integrates with Google GenAI SDK (gemini-3.6-flash / configured LLM_MODEL)
    and streams responses back to the client.
    """

    def __init__(self):
        self._client = None
        self._cached_key = None

    def get_client(self) -> Optional[genai.Client]:
        """
        Dynamically gets or initializes the GenAI client.
        Re-evaluates environment variables on each call so updating .env or environment
        takes effect immediately without server restart.
        """
        load_dotenv()
        current_key = (
            os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or ""
        ).strip()

        if not current_key:
            return None

        if self._client is None or self._cached_key != current_key:
            try:
                self._client = genai.Client(api_key=current_key)
                self._cached_key = current_key
            except Exception as e:
                logger.error(f"Failed to initialize GenAI client: {e}")
                return None

        return self._client

    @property
    def model(self) -> str:
        return os.environ.get("LLM_MODEL", "gemini-3.5-flash-lite").strip()

    def _format_contents(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        context: Optional[Dict] = None,
    ) -> List[types.Content]:
        """Converts incoming history and current message into GenAI Content objects."""
        contents: List[types.Content] = []

        # Optional client context hint (e.g. active view or case ID)
        context_prefix = ""
        if context:
            ctx_items = []
            if context.get("activeView"):
                ctx_items.append(f"Active View: {context['activeView']}")
            if context.get("investigationId"):
                ctx_items.append(f"Current Investigation: {context['investigationId']}")
            if ctx_items:
                context_prefix = f"[UI Context: {', '.join(ctx_items)}]\n"

        # Format history
        if history:
            for item in history:
                role = item.get("role")
                content_text = item.get("content", "")
                if not content_text:
                    continue

                genai_role = "user" if role == "user" else "model"
                contents.append(
                    types.Content(
                        role=genai_role,
                        parts=[types.Part.from_text(text=content_text)],
                    )
                )

        # Current user message with context prefix
        full_message = f"{context_prefix}{message}"
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=full_message)],
            )
        )

        return contents

    async def stream_chat_response(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        user_name: Optional[str] = None,
        user_role: Optional[str] = None,
        context: Optional[Dict] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Streams AI response chunks asynchronously.

        Yields SSE format chunks (e.g., "data: {\"text\": \"...\"}\n\n").
        Handles API errors and unconfigured keys safely without exposing internal secrets.
        """
        system_instruction = build_system_instruction(user_name=user_name, user_role=user_role)
        client = self.get_client()

        # Check if LLM client is available
        if not client:
            fallback_msg = (
                "DarKnight AI copilot is currently operating in offline mode. "
                "For live AI streaming, please ensure a valid `LLM_API_KEY` is configured in `backend/.env`.\n\n"
                "In the meantime, you can ask platform workflow questions or consult the DarKnight documentation!"
            )
            yield f"data: {{\"text\": {self._json_dumps(fallback_msg)}}}\n\n"
            yield "data: [DONE]\n\n"
            return

        try:
            contents = self._format_contents(message=message, history=history, context=context)

            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.3,
            )

            loop = asyncio.get_running_loop()
            models_to_try = [self.model, "gemini-2.5-flash", "gemini-1.5-flash"]
            # Deduplicate preserving order
            models_to_try = list(dict.fromkeys(models_to_try))

            response_stream = None
            last_error = None

            for model_name in models_to_try:
                try:
                    def _get_stream(m=model_name):
                        return client.models.generate_content_stream(
                            model=m,
                            contents=contents,
                            config=config,
                        )

                    response_stream = await loop.run_in_executor(None, _get_stream)
                    break
                except Exception as model_err:
                    last_error = model_err
                    logger.warning(f"Failed generation with model '{model_name}': {model_err}")

            if not response_stream:
                if last_error:
                    raise last_error
                else:
                    raise RuntimeError("Failed to obtain response stream from GenAI API.")

            # Stream chunks as they arrive
            for chunk in response_stream:
                if chunk.text:
                    yield f"data: {{\"text\": {self._json_dumps(chunk.text)}}}\n\n"

            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Error during AI streaming response: {e}")
            err_msg = "DarKnight AI couldn't process that request right now. Please verify your API key or network connection."
            yield f"data: {{\"text\": {self._json_dumps(err_msg)}}}\n\n"
            yield "data: [DONE]\n\n"

    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
    ) -> tuple[str, str]:
        """
        Non-streaming text generation reusing dynamic get_client() and model fallbacks.

        Returns:
            Tuple of (generated_text, model_name_used).

        Raises:
            RuntimeError if client is unconfigured or all model generations fail.
        """
        client = self.get_client()
        if not client:
            raise RuntimeError("LLM_API_KEY_NOT_CONFIGURED")

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
        )

        models_to_try = [self.model, "gemini-2.5-flash", "gemini-1.5-flash"]
        # Deduplicate preserving order
        models_to_try = list(dict.fromkeys(models_to_try))

        last_error = None
        for model_name in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config,
                )
                if response and response.text:
                    return response.text, model_name
            except Exception as model_err:
                last_error = model_err
                logger.warning(f"Failed non-streaming generation with model '{model_name}': {model_err}")

        if last_error:
            raise last_error
        raise RuntimeError("Failed to obtain response from GenAI API.")

    @staticmethod
    def _json_dumps(text: str) -> str:
        import json
        return json.dumps(text)


# Global singleton instance
ai_service = AIService()
