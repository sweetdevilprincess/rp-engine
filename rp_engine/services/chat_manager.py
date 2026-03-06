"""Chat manager — orchestrates the full RP chat pipeline.

Chains together: context retrieval -> prompt assembly -> LLM call -> exchange save.
Handles both non-streaming and streaming responses.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from rp_engine.config import ChatConfig
from rp_engine.database import PRIORITY_EXCHANGE, Database
from rp_engine.models.chat import ChatResponse
from rp_engine.models.context import ContextRequest, ContextResponse
from rp_engine.services.analysis_pipeline import AnalysisPipeline
from rp_engine.services.context_engine import ContextEngine
from rp_engine.services.lance_store import LanceStore
from rp_engine.services.llm_client import LLMClient
from rp_engine.services.prompt_assembler import PromptAssembler

logger = logging.getLogger(__name__)


class ChatManager:
    """Orchestrates the full RP chat pipeline."""

    def __init__(
        self,
        db: Database,
        context_engine: ContextEngine,
        prompt_assembler: PromptAssembler,
        llm_client: LLMClient,
        analysis_pipeline: AnalysisPipeline,
        lance_store: LanceStore,
        config: ChatConfig,
    ) -> None:
        self.db = db
        self.context_engine = context_engine
        self.prompt_assembler = prompt_assembler
        self.llm_client = llm_client
        self.analysis_pipeline = analysis_pipeline
        self.lance_store = lance_store
        self.config = config

    async def chat(
        self,
        user_message: str,
        rp_folder: str,
        branch: str,
        session_id: str,
    ) -> ChatResponse:
        """Full non-streaming chat pipeline.

        1. Run context pipeline
        2. Build prompt messages
        3. Call LLM
        4. Save exchange
        5. Return response
        """
        # 1. Context
        context_response = await self._get_context(user_message, rp_folder, branch, session_id)

        # 2. Build messages
        messages = await self.prompt_assembler.build_messages(
            rp_folder=rp_folder,
            branch=branch,
            user_message=user_message,
            context_response=context_response,
            session_id=session_id,
        )

        # 3. Call LLM
        model = self.config.model or self.llm_client._fallback
        llm_response = await self.llm_client.generate(
            messages=messages,
            model=model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

        # 4. Save exchange
        exchange_id, exchange_number = await self._save_exchange(
            rp_folder=rp_folder,
            branch=branch,
            session_id=session_id,
            user_message=user_message,
            assistant_response=llm_response.content,
        )

        # 5. Build context summary
        context_summary = self._build_context_summary(context_response)

        return ChatResponse(
            response=llm_response.content,
            exchange_id=exchange_id,
            exchange_number=exchange_number,
            session_id=session_id,
            context_summary=context_summary,
        )

    async def chat_stream(
        self,
        user_message: str,
        rp_folder: str,
        branch: str,
        session_id: str,
    ) -> AsyncIterator[str]:
        """Streaming chat pipeline. Yields SSE-formatted events.

        1. Run context pipeline
        2. Build prompt messages
        3. Stream LLM response (yielding tokens)
        4. After stream completes: save exchange
        5. Yield done event
        """
        # 1. Context
        context_response = await self._get_context(user_message, rp_folder, branch, session_id)

        # 2. Build messages
        messages = await self.prompt_assembler.build_messages(
            rp_folder=rp_folder,
            branch=branch,
            user_message=user_message,
            context_response=context_response,
            session_id=session_id,
        )

        # 3. Stream LLM
        model = self.config.model or self.llm_client._fallback
        full_response: list[str] = []

        async for chunk in self.llm_client.generate_stream(
            messages=messages,
            model=model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        ):
            full_response.append(chunk)
            yield f'data: {{"type": "token", "content": {_json_escape(chunk)}}}\n\n'

        # 4. Save exchange
        response_text = "".join(full_response)
        exchange_id, exchange_number = await self._save_exchange(
            rp_folder=rp_folder,
            branch=branch,
            session_id=session_id,
            user_message=user_message,
            assistant_response=response_text,
        )

        # 5. Done event
        yield (
            f'data: {{"type": "done", "exchange_id": {exchange_id}, '
            f'"exchange_number": {exchange_number}}}\n\n'
        )

    async def _get_context(
        self,
        user_message: str,
        rp_folder: str,
        branch: str,
        session_id: str,
    ) -> ContextResponse:
        """Run the context pipeline."""
        request = ContextRequest(
            user_message=user_message,
            include_npc_reactions=False,
        )
        return await self.context_engine.get_context(
            request=request,
            rp_folder=rp_folder,
            branch=branch,
            session_id=session_id,
        )

    async def _save_exchange(
        self,
        rp_folder: str,
        branch: str,
        session_id: str,
        user_message: str,
        assistant_response: str,
    ) -> tuple[int, int]:
        """Save exchange to DB, enqueue for analysis, embed in vector store."""
        # Get next exchange number
        latest = await self.db.fetch_val(
            "SELECT MAX(exchange_number) FROM exchanges WHERE rp_folder = ? AND branch = ?",
            [rp_folder, branch],
        )
        exchange_number = (latest or 0) + 1
        now = datetime.now(UTC).isoformat()

        content_hash = hashlib.sha256(
            (user_message + assistant_response).encode()
        ).hexdigest()[:16]

        future = await self.db.enqueue_write(
            """INSERT INTO exchanges (session_id, rp_folder, branch, exchange_number,
               user_message, assistant_response, analysis_status, created_at, idempotency_key)
               VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
            [
                session_id,
                rp_folder,
                branch,
                exchange_number,
                user_message,
                assistant_response,
                now,
                content_hash,
            ],
            priority=PRIORITY_EXCHANGE,
        )
        exchange_id = await future

        # Background vector embedding
        if self.lance_store is not None:
            async def _embed():
                try:
                    await self.lance_store.embed_exchange(
                        exchange_number=exchange_number,
                        user_message=user_message,
                        assistant_response=assistant_response,
                        rp_folder=rp_folder,
                        branch=branch,
                        session_id=session_id,
                    )
                except Exception as e:
                    logger.warning("Chat embedding failed: %s", e)
            asyncio.create_task(_embed())

        # Enqueue for analysis
        if self.analysis_pipeline is not None:
            await self.analysis_pipeline.enqueue(exchange_id, rp_folder, branch)

        logger.info(
            "Chat exchange %d (id=%d) saved for session %s",
            exchange_number, exchange_id, session_id,
        )

        return exchange_id, exchange_number

    def _build_context_summary(self, ctx: ContextResponse) -> dict:
        """Build a minimal summary of what context was used."""
        return {
            "documents": len(ctx.documents),
            "npc_briefs": [b.character for b in ctx.npc_briefs],
            "thread_alerts": len(ctx.thread_alerts),
            "past_exchanges": len(ctx.past_exchanges),
            "scene_location": ctx.scene_state.location if ctx.scene_state else None,
        }


def _json_escape(s: str) -> str:
    """Escape a string for JSON embedding in SSE data."""
    import json
    return json.dumps(s)
