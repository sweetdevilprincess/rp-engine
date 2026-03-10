"""Continuity checker — detects narrative contradictions in exchanges.

Runs as an optional step in the analysis pipeline. Extracts checkable facts
from the current exchange's analysis, searches past exchanges for the same
entities, and uses LLM comparison to detect contradictions.

Disabled by default (config.continuity.enabled = false) to avoid extra LLM cost.
"""

from __future__ import annotations

import json
import logging

from rp_engine.config import ContinuityConfig
from rp_engine.database import PRIORITY_ANALYSIS, Database
from rp_engine.models.analysis import AnalysisLLMResult
from rp_engine.models.continuity import ContinuityFact, ContinuityWarning
from rp_engine.services.llm_client import LLMClient

logger = logging.getLogger(__name__)


class ContinuityChecker:
    """Detects narrative contradictions by comparing current facts to past exchanges."""

    def __init__(
        self,
        db: Database,
        llm_client: LLMClient,
        config: ContinuityConfig,
        lance_store=None,
    ) -> None:
        self.db = db
        self.llm = llm_client
        self.config = config
        self.lance_store = lance_store

    async def check_exchange(
        self,
        exchange_id: int,
        analysis: AnalysisLLMResult,
        rp_folder: str,
        branch: str = "main",
    ) -> list[ContinuityWarning]:
        """Check an exchange for continuity issues.

        Extracts facts from the analysis result, searches for contradictions
        in past exchanges, and stores any warnings found.
        """
        if not self.config.enabled:
            return []

        exchange = await self.db.fetch_one(
            "SELECT exchange_number FROM exchanges WHERE id = ?", [exchange_id]
        )
        if not exchange:
            return []

        exchange_number = exchange["exchange_number"]
        facts = self._extract_facts(analysis, exchange_number)
        if not facts:
            return []

        warnings: list[ContinuityWarning] = []
        for fact in facts:
            contradictions = await self._check_fact(fact, rp_folder, branch)
            warnings.extend(contradictions)

        # Store warnings
        for w in warnings:
            await self.db.enqueue_write(
                """INSERT INTO continuity_warnings
                       (rp_folder, branch, entity_name, category,
                        current_claim, current_exchange,
                        past_claim, past_exchange,
                        severity, explanation)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [rp_folder, branch, w.entity_name, w.category,
                 w.current_claim, w.current_exchange,
                 w.past_claim, w.past_exchange,
                 w.severity, w.explanation],
                priority=PRIORITY_ANALYSIS,
            )

        if warnings:
            logger.info(
                "Continuity check for exchange %d found %d issue(s)",
                exchange_id, len(warnings),
            )

        return warnings

    def _extract_facts(
        self, analysis: AnalysisLLMResult, exchange_number: int
    ) -> list[ContinuityFact]:
        """Extract checkable facts from an analysis result.

        Focuses on location claims and character status — the most
        clear-cut categories for contradiction detection.
        """
        facts: list[ContinuityFact] = []

        # Character locations
        for char_name, char_state in analysis.story_state.characters.items():
            if char_state.location:
                facts.append(ContinuityFact(
                    entity_name=char_name,
                    category="location",
                    claim=f"{char_name} is at {char_state.location}",
                    exchange_number=exchange_number,
                ))

            # Character conditions (injured, dead, etc.)
            for condition in char_state.conditions:
                if condition:
                    facts.append(ContinuityFact(
                        entity_name=char_name,
                        category="status",
                        claim=f"{char_name} is {condition}",
                        exchange_number=exchange_number,
                    ))

        # Scene location
        sc = analysis.story_state.scene_context
        if sc.location:
            facts.append(ContinuityFact(
                entity_name=sc.location,
                category="location",
                claim=f"Scene is at {sc.location}",
                exchange_number=exchange_number,
            ))

        return facts

    async def _check_fact(
        self,
        fact: ContinuityFact,
        rp_folder: str,
        branch: str,
    ) -> list[ContinuityWarning]:
        """Search past exchanges for contradictions to a fact."""
        if not self.lance_store:
            return []

        # Search past exchanges for mentions of this entity
        search_query = f"{fact.entity_name} {fact.category}"
        results = await self.lance_store.search_exchanges(
            query_text=search_query,
            rp_folder=rp_folder,
            branch=branch,
            limit=self.config.max_search_results,
            max_exchange=fact.exchange_number - 1,
        )

        if not results:
            return []

        # Filter results that actually mention the entity
        relevant = [
            r for r in results
            if fact.entity_name.lower() in r.text.lower()
            and r.score >= self.config.min_similarity
        ]

        if not relevant:
            return []

        # LLM comparison — batch relevant past claims
        past_claims = "\n".join(
            f"- Exchange #{r.metadata.get('exchange_number', '?')}: {r.text[:300]}"
            for r in relevant[:3]
        )

        prompt = f"""You are checking for narrative continuity issues.

Current fact (Exchange #{fact.exchange_number}):
"{fact.claim}"

Past references to "{fact.entity_name}":
{past_claims}

Does the current fact CONTRADICT any past reference? Consider:
- Characters can move to new locations (not a contradiction)
- Conditions can change over time (not a contradiction)
- Only flag CLEAR contradictions where both claims cannot be true simultaneously
- Ignore minor wording differences

Respond with JSON:
{{"contradictions": [{{"past_exchange": <number>, "past_claim": "<summary>", "severity": "info|warning|conflict", "explanation": "<brief reason>"}}]}}

If no contradictions, respond: {{"contradictions": []}}"""

        try:
            response = await self.llm.generate(
                messages=[{"role": "user", "content": prompt}],
                model=self.llm.models.response_analysis,
                temperature=0.1,
                max_tokens=500,
            )

            parsed = self._parse_llm_response(response.content)
            warnings: list[ContinuityWarning] = []
            for c in parsed:
                warnings.append(ContinuityWarning(
                    rp_folder=rp_folder,
                    branch=branch,
                    entity_name=fact.entity_name,
                    category=fact.category,
                    current_claim=fact.claim,
                    current_exchange=fact.exchange_number,
                    past_claim=c.get("past_claim", ""),
                    past_exchange=c.get("past_exchange", 0),
                    severity=c.get("severity", "warning"),
                    explanation=c.get("explanation"),
                ))
            return warnings
        except Exception as e:
            logger.warning("Continuity LLM check failed: %s", e)
            return []

    @staticmethod
    def _parse_llm_response(content: str) -> list[dict]:
        """Parse the LLM contradiction response, handling various formats."""
        content = content.strip()
        # Strip markdown code fences if present
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(
                line for line in lines if not line.strip().startswith("```")
            )

        try:
            data = json.loads(content)
            contradictions = data.get("contradictions", [])
            return contradictions if isinstance(contradictions, list) else []
        except (json.JSONDecodeError, AttributeError):
            return []

    async def get_warnings(
        self,
        rp_folder: str,
        branch: str = "main",
        resolved: bool | None = None,
    ) -> list[ContinuityWarning]:
        """Fetch continuity warnings from the database."""
        query = """SELECT * FROM continuity_warnings
                   WHERE rp_folder = ? AND branch = ?"""
        params: list = [rp_folder, branch]

        if resolved is not None:
            query += " AND resolved = ?"
            params.append(1 if resolved else 0)

        query += " ORDER BY created_at DESC"
        rows = await self.db.fetch_all(query, params)

        return [
            ContinuityWarning(
                id=r["id"],
                rp_folder=r["rp_folder"],
                branch=r["branch"],
                entity_name=r["entity_name"],
                category=r["category"],
                current_claim=r["current_claim"],
                current_exchange=r["current_exchange"],
                past_claim=r["past_claim"],
                past_exchange=r["past_exchange"],
                severity=r["severity"],
                explanation=r.get("explanation"),
                resolved=bool(r["resolved"]),
                resolved_reason=r.get("resolved_reason"),
            )
            for r in rows
        ]

    async def resolve_warning(
        self, warning_id: int, reason: str
    ) -> bool:
        """Mark a warning as resolved with a reason."""
        future = await self.db.enqueue_write(
            """UPDATE continuity_warnings
               SET resolved = 1, resolved_reason = ?
               WHERE id = ?""",
            [reason, warning_id],
            priority=PRIORITY_ANALYSIS,
        )
        await future
        return True
