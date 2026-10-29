"""
services/mirofish_service.py — Service to interact with external MiroFish-Offline Engine.
"""

import httpx
import json
import asyncio
import io
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, AsyncGenerator
from app.config import settings
from app.schemas.prd import PRDDocument
from app.schemas import Stakeholder, StakeholderProposalResponse
from app.services.llm_provider import get_llm_service

logger = logging.getLogger("app.services.mirofish")

class MiroFishService:
    def __init__(self):
        self.base_url = settings.mirofish_base_url
        self.timeout = httpx.Timeout(settings.mirofish_timeout)
        self.llm_base_url = settings.openai_api_base
        self.llm_key = settings.openai_api_key
        self.llm_model = settings.openai_model_name

    async def _call_stakeholder_llm(self, system_prompt: str, user_prompt: str) -> str:
        """
        Send a single system+user prompt to whichever LLM backend is
        configured (Claude, real OpenAI, or the local Ollama OpenAI-compatible
        endpoint) and return the raw assistant text.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if settings.llm_provider in ("claude", "openai"):
            return await get_llm_service().chat(messages)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                self.llm_base_url + "/chat/completions",
                headers={"Authorization": f"Bearer {self.llm_key}"},
                json={
                    "model": self.llm_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "response_format": {"type": "json_object"}
                }
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    def _parse_stakeholders_lenient(self, data: Dict[str, Any]) -> List[Stakeholder]:
        """
        Parse the 'stakeholders' array item-by-item, skipping any single
        malformed entry instead of discarding the whole batch (Ollama's
        JSON mode occasionally produces one off-schema item among 8-12).
        """
        raw_items = data.get("stakeholders", [])
        stakeholders: List[Stakeholder] = []
        for i, item in enumerate(raw_items):
            try:
                stakeholders.append(Stakeholder(**item))
            except Exception as item_err:
                logger.warning(f"Skipping malformed stakeholder at index {i}: {item_err}. Raw item: {item}")
        return stakeholders

    async def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        # Ensure path starts with /api/ unless it's a direct endpoint like /health
        normalized_path = path.lstrip('/')
        if not normalized_path.startswith("api/") and normalized_path not in ("health", "health/"):
            path = f"/api/{normalized_path}"
        else:
            path = f"/{normalized_path}"
            
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            url = f"{self.base_url.rstrip('/')}{path}"
            logger.debug(f"MiroFish Request: {method} {url}")
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()


    async def propose_stakeholders_from_dict(self, payload: Dict[str, Any]) -> List[Stakeholder]:
        """
        Analyze partial PRD (as dict) and propose stakeholders.
        """
        # Convert enough of the dict to markdown for the LLM
        md = self._convert_dict_to_markdown(payload)
        
        prompt = f"""
        Analyze the following partial PRD and identify all necessary stakeholders for a rigorous simulation.
        The number of stakeholders should vary based on project complexity (typically 8-12).
        
        You MUST think highly intelligently and include a profoundly diverse group of participants representing all major direct and indirect perspectives:
        1. Customers & End Users: B2B/B2C users who care about reliability, usability, privacy, and accuracy.
        2. Competitors: Analytical personas advocating for competitor viewpoints or trying to point out market disadvantages.
        3. Quality & Testing: QA or Quality Control Managers focused on robustness, edge cases, system limits, and failure points.
        4. Operations & Scaling: Devops, infrastructure, or maintenance managers focused on hosting, cost, scaling, and integration.
        5. Core Roles: Product Manager, Lead Developer/Architect, Security Auditor.
        6. Ecosystem & Business (CRITICAL): B2B Sales Leaders (focused on enterprise deal-closing and compliance barriers), CS Training & HR Managers (focused on internal employee upsell, labor unions, and job displacement anxieties), or Vendor/Seller Representatives (focused on monetary leaks, platform commissions, and delegation of authority).
        7. Regulatory & Compliance: Legal Counsel or Government/Regulatory Certification Auditors (focused on ISMS-P, CSAP, and liabilities for AI errors).
        
        For each stakeholder, provide:
        1. name: A realistic name and title in the primary language of the PRD (Korean).
        2. role: Their specific function (e.g., Competitor Analyst, QA Lead, CS Trainer, CFO, B2B Client, ISMS-P Auditor).
        3. review_angle: A detailed, highly insightful description of what aspect of the PRD this stakeholder evaluates, including their professional background, priorities, and specific biases.
           (e.g., "금융권 및 대기업의 개인정보 유출 리스크 원천 봉쇄 및 CSAP/ISMS-P 인증 규제 통과 가능성 검토", "비표준 레거시 연동 배제 및 E2E Latency 1.5초 달성을 위한 아키텍처 가용성 분석").
        4. likely_objections: An array of anticipated objections or challenges this stakeholder might vigorously raise during simulation.

        You MUST generate at least 8 to 12 distinct, high-quality stakeholders matching the domain complexity. Do not simplify or return fewer personas.

        PRD Content:
        {md}

        Return result as JSON object with 'stakeholders' key.
        JSON format for each stakeholder: {{ "name": "...", "role": "...", "review_angle": "...", "likely_objections": ["...", "..."] }}
        IMPORTANT: Return the response in the PRIMARY LANGUAGE of the PRD content (Korean).
        """
        
        data_content = await self._call_stakeholder_llm(
            system_prompt="You are a product management consultant expert in stakeholder analysis. Always return Korean names and responses.",
            user_prompt=prompt,
        )
        logger.debug(f"LLM Stakeholder Response (dict mode): {data_content}")

        try:
            result = self._extract_json(data_content)
            stakeholders = self._parse_stakeholders_lenient(result)
        except Exception as je:
            logger.error(f"JSON Parse Error (dict mode): {je}. Raw: {data_content}")
            raise je
        if not stakeholders:
            raise ValueError(f"No valid stakeholders parsed from LLM response (dict mode). Raw: {data_content}")
        return stakeholders

    async def propose_stakeholders(self, prd: PRDDocument) -> List[Stakeholder]:
        """
        Analyze PRD and propose a list of stakeholders with personas.
        """
        prd_md = self._convert_prd_to_markdown(prd)
        
        prompt = f"""
        Analyze the following Product Requirements Document (PRD) and identify all necessary stakeholders 
        to perform a rigorous stress-test. The number of stakeholders should vary based on project complexity (typically 8-12).
        
        You MUST think highly intelligently and include a profoundly diverse group of participants representing all major direct and indirect perspectives:
        1. Customers & End Users: B2B/B2C users who care about reliability, usability, privacy, and accuracy.
        2. Competitors: Analytical personas advocating for competitor viewpoints or trying to point out market disadvantages.
        3. Quality & Testing: QA or Quality Control Managers focused on robustness, edge cases, system limits, and failure points.
        4. Operations & Scaling: Devops, infrastructure, or maintenance managers focused on hosting, cost, scaling, and integration.
        5. Core Roles: Product Manager, Lead Developer/Architect, Security Auditor.
        6. Ecosystem & Business (CRITICAL): B2B Sales Leaders (focused on enterprise deal-closing and compliance barriers), CS Training & HR Managers (focused on internal employee upsell, labor unions, and job displacement anxieties), or Vendor/Seller Representatives (focused on monetary leaks, platform commissions, and delegation of authority).
        7. Regulatory & Compliance: Legal Counsel or Government/Regulatory Certification Auditors (focused on ISMS-P, CSAP, and liabilities for AI errors).
        
        For each stakeholder, provide:
        1. name: A realistic name and title in the primary language of the PRD (Korean).
        2. role: Their specific function (e.g., Competitor Analyst, QA Lead, CS Trainer, CFO, B2B Client, ISMS-P Auditor).
        3. review_angle: A detailed, highly insightful description of what aspect of the PRD this stakeholder evaluates, including their professional background, priorities, and specific biases.
           (e.g., "금융권 및 대기업의 개인정보 유출 리스크 원천 봉쇄 및 CSAP/ISMS-P 인증 규제 통과 가능성 검토", "비표준 레거시 연동 배제 및 E2E Latency 1.5초 달성을 위한 아키텍처 가용성 분석").
        4. likely_objections: An array of anticipated objections or challenges this stakeholder might vigorously raise during simulation.

        You MUST generate at least 8 to 12 distinct, high-quality stakeholders matching the domain complexity. Do not simplify or return fewer personas.

        PRD Content:
        {prd_md}

        IMPORTANT: Return the response in the PRIMARY LANGUAGE of the PRD content above (Korean).
        Return result as a JSON object with a 'stakeholders' key containing an array of objects.
        """

        content = await self._call_stakeholder_llm(
            system_prompt="You are a product management consultant expert in stakeholder analysis. Always return Korean names and responses.",
            user_prompt=prompt,
        )
        logger.debug(f"LLM Stakeholder Response: {content}")

        try:
            data = self._extract_json(content)
            stakeholders = self._parse_stakeholders_lenient(data)
        except Exception as je:
            logger.error(f"JSON Parse Error for stakeholders: {je}. Raw content: {content}")
            raise je
        if not stakeholders:
            raise ValueError(f"No valid stakeholders parsed from LLM response. Raw content: {content}")
        return stakeholders

    async def setup_project_and_graph(self, prd: PRDDocument) -> Dict[str, str]:
        """
        Step 1 & 2: Upload PRD as file -> Generate Ontology -> Build Graph
        """
        # 1. Convert PRD to Markdown content
        prd_md = self._convert_prd_to_markdown(prd)
        
        # 2. Upload and Generate Ontology
        files = {
            'files': ('prd.md', io.BytesIO(prd_md.encode('utf-8')), 'text/markdown')
        }
        data = {
            'simulation_requirement': prd.validation.simulation_requirement or prd.product.one_liner,
            'project_name': prd.product.name,
            'additional_context': prd.product.one_liner
        }
        
        logger.info("Initializing MiroFish project...")
        onto_resp = await self._request("POST", "/graph/ontology/generate", data=data, files=files)
        project_id = onto_resp["data"]["project_id"]
        
        # 3. Build Graph
        logger.info(f"Building MiroFish graph for project {project_id}...")
        build_resp = await self._request("POST", "/graph/build", json={"project_id": project_id})
        task_id = build_resp["data"]["task_id"]

        # Only a completed engine task can supply a usable graph ID.
        graph_id = await self._wait_for_task(task_id)
        
        return {
            "project_id": project_id,
            "graph_id": graph_id
        }
        
    async def setup_project_and_graph_from_dict(self, payload: Dict[str, Any]) -> Dict[str, str]:
        """
        Fallback setup for partial PRD.
        """
        prd_md = self._convert_dict_to_markdown(payload)
        
        # Basic info extraction from the dict
        product_info = payload.get("product", {})
        project_name = product_info.get("name", "New Project")
        one_liner = product_info.get("one_liner", "A new AI product.")
        
        files = {
            'files': ('prd.md', io.BytesIO(prd_md.encode('utf-8')), 'text/markdown')
        }
        data = {
            'simulation_requirement': one_liner,
            'project_name': project_name,
            'additional_context': one_liner
        }
        
        logger.info(f"Initializing MiroFish project for {project_name} (partial)...")
        onto_resp = await self._request("POST", "/graph/ontology/generate", data=data, files=files)
        project_id = onto_resp["data"]["project_id"]
        
        # Build Graph
        build_resp = await self._request("POST", "/graph/build", json={"project_id": project_id})
        task_id = build_resp["data"]["task_id"]
        graph_id = await self._wait_for_task(task_id)
        
        return {
            "project_id": project_id,
            "graph_id": graph_id
        }

    async def create_and_start_simulation(
        self, 
        project_id: str, 
        graph_id: str,
        requirement: Optional[str] = None
    ) -> str:
        # Note: MiroFish-Offline engine does not support updating project requirements via PATCH /project/{project_id}.
        # The simulation_requirement is already defined during the ontology generation step.
        logger.info(f"Skipping project requirement PATCH for {project_id} (not supported by offline engine)")

        logger.info(f"Creating MiroFish simulation for project {project_id}...")
        create_resp = await self._request("POST", "/simulation/create", json={
            "project_id": project_id,
            "graph_id": graph_id
        })
        simulation_id = create_resp["data"]["simulation_id"]
        
        # 4. Prepare Simulation
        logger.info(f"Preparing MiroFish simulation {simulation_id} with {settings.mirofish_agent_count} agents...")
        prep_resp = await self._request("POST", "/simulation/prepare", json={
            "simulation_id": simulation_id,
            "parallel_profile_count": settings.mirofish_agent_count
        })
        task_id = prep_resp["data"]["task_id"]

        # Poll prepare/status until it is ready/completed
        logger.info(f"Polling prepare status for task {task_id}...")
        max_attempts = settings.mirofish_max_polling
        interval = settings.mirofish_polling_interval

        for attempt in range(max_attempts):
            status_resp = await self._request("POST", "/simulation/prepare/status", json={
                "task_id": task_id,
                "simulation_id": simulation_id
            })
            status_val = str(status_resp.get("data", {}).get("status") or "").lower()
            logger.info(f"Prepare status polling attempt {attempt+1}/{max_attempts}: {status_val}")

            if status_val in ("ready", "completed", "done"):
                logger.info("Simulation preparation complete!")
                break
            if status_val in ("failed", "error"):
                raise Exception(f"Simulation prepare failed: {status_resp.get('data', {}).get('error')}")

            await asyncio.sleep(interval)
        else:
            raise Exception("Simulation prepare timed out.")
        
        # 5. Start Simulation
        logger.info(f"Starting MiroFish simulation {simulation_id} with max_rounds={settings.mirofish_max_rounds}...")
        await self._request("POST", "/simulation/start", json={
            "simulation_id": simulation_id,
            "platform": "parallel",
            "max_rounds": settings.mirofish_max_rounds,
            "enable_graph_memory_update": settings.mirofish_enable_memory
        })
        
        return simulation_id

    async def poll_events(self, simulation_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Poll simulation actions and yield them as events.
        """
        last_action_count = 0
        while True:
            try:
                resp = await self._request("GET", f"/simulation/{simulation_id}/run-status/detail")
                data = resp["data"]
                status = data.get("runner_status")
                all_actions = data.get("all_actions", [])
                # The engine reports 0..100; the browser SSE contract is 0..1.
                progress = max(0.0, min(float(data.get("progress_percent") or 0) / 100, 1.0))
                
                # Yield new actions
                if len(all_actions) > last_action_count:
                    for i, action in enumerate(all_actions[last_action_count:]):
                        event = self._map_action_to_event(
                            action, 
                            progress if i == len(all_actions[last_action_count:]) - 1 else progress * 0.9
                        )
                        yield event
                    last_action_count = len(all_actions)
                
                if status in ["completed", "failed", "stopped"]:
                    if status == "completed":
                         yield {
                             "type": "simulation_complete", 
                             "content": "Simulation finished successfully. Analysis report is being prepared.", 
                             "timestamp": datetime.now().isoformat(),
                             "progress": 1.0
                         }
                    else:
                        yield {
                            "type": "simulation_error",
                            "content": data.get("error") or f"MiroFish simulation {status}.",
                            "timestamp": datetime.now().isoformat(),
                            "progress": progress,
                            "mode": "live",
                        }
                    break
                    
                await asyncio.sleep(settings.mirofish_polling_interval)
                
            except Exception as e:
                logger.error(f"Error polling MiroFish events: {e}")
                yield {"type": "agent_post", "agent_name": "System", "agent_type": "Log", "content": f"Connection update: {str(e)}", "timestamp": datetime.now().isoformat()}
                await asyncio.sleep(5)

    async def _wait_for_task(self, task_id: str) -> str:
        """Poll task until completion."""
        max_attempts = settings.mirofish_max_polling
        interval = settings.mirofish_polling_interval
        
        for _ in range(max_attempts):
            resp = await self._request("GET", f"/graph/task/{task_id}")
            task_data = resp["data"]
            status = task_data.get("status")
            
            if status == "completed":
                return task_data["result"]["graph_id"]
            if status == "failed":
                raise Exception(f"MiroFish task {task_id} failed: {task_data.get('error')}")
                
            await asyncio.sleep(interval)
            
        raise Exception(f"MiroFish task {task_id} timed out.")

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON object from text, handling markdown code blocks."""
        # Try to find JSON in code blocks first
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            text = match.group(1)
        
        # Strip potential leading/trailing whitespace
        text = text.strip()
        
        # If it's empty after stripping, raise
        if not text:
            raise ValueError("Empty content after JSON extraction")
            
        return json.loads(text)

    def _convert_prd_to_markdown(self, prd: PRDDocument) -> str:
        """Simple conversion of PRD document to Markdown."""
        md = f"# PRD: {prd.product.name}\n\n"
        md += f"## One Liner\n{prd.product.one_liner}\n\n"
        md += f"## Core Problem\n{prd.problem.core_problem}\n\n"
        md += "## Pain Points\n" + "\n".join([f"- {p}" for p in (prd.problem.pain_points or [])]) + "\n\n"
        md += "## Functional Requirements\n" + "\n".join([f"- {r.statement}" for r in (prd.requirements.functional or [])]) + "\n\n"
        md += "## Target Personas (End Users)\n" + "\n".join([f"- {p.name} ({p.role}): {', '.join(p.goals)}" for p in (prd.users.primary_personas or [])]) + "\n\n"
        
        # Inject Custom Stakeholders for MiroFish Agent Generation
        if prd.validation and prd.validation.stakeholder_personas:
            md += "# Stakeholders\n"
            for s in prd.validation.stakeholder_personas:
                md += f"### {s.name}\n"
                md += f"- **Role**: {s.role}\n"
                md += f"- **Review Angle**: {s.review_angle}\n"
                md += f"- **Likely Objections**: {', '.join(s.likely_objections) if s.likely_objections else 'None'}\n\n"
        
        return md

    def _convert_dict_to_markdown(self, payload: Dict[str, Any]) -> str:
        """Heuristic conversion of raw dict to markdown with rich context."""
        product = payload.get("product", {})
        problem = payload.get("problem", {})
        users = payload.get("users", {})
        requirements = payload.get("requirements", {})
        scope = payload.get("scope", {})
        
        md = f"# PRD: {product.get('name', 'Draft')}\n\n"
        md += f"## Summary\n{product.get('one_liner', 'No summary provided')}\n\n"
        md += f"## Problem\n{problem.get('core_problem', 'No problem defined yet')}\n\n"
        
        if users.get("primary_personas"):
            md += "## Target Users\n"
            for u in users["primary_personas"]:
                goals = u.get("goals", [])
                goals_str = ", ".join(goals) if isinstance(goals, list) else str(goals)
                md += f"- {u.get('name')} ({u.get('role')}): {goals_str}\n"
            md += "\n"
            
        if requirements.get("functional"):
            md += "## Functional Requirements\n"
            for r in requirements["functional"]:
                md += f"- {r.get('statement')} (Priority: {r.get('priority')})\n"
            md += "\n"
            
        if scope:
            md += f"## Scope: In Scope\n"
            for item in scope.get("in_scope", []):
                md += f"- {item}\n"
            md += "\n"

        if "validation" in payload and "stakeholder_personas" in payload["validation"]:
            md += "# Existing Stakeholders\n"
            for s in payload["validation"]["stakeholder_personas"]:
                objections = s.get("likely_objections", [])
                obj_str = ", ".join(objections) if isinstance(objections, list) else str(objections)
                md += f"### {s.get('name')}\n"
                md += f"- **Role**: {s.get('role')}\n"
                md += f"- **Review Angle**: {s.get('review_angle')}\n"
                md += f"- **Likely Objections**: {obj_str}\n\n"
                
        return md

    def _map_action_to_event(self, action: Dict[str, Any], progress: float) -> Dict[str, Any]:
        """Convert MiroFish internal action to frontend Event format."""
        content = action.get("action_args", {}).get("content", "")
        if not content and action.get("action_type") == "COMMENT":
             content = action.get("action_args", {}).get("text", "")
        
        agent_role = action.get("agent_role", "Participant")
        platform = action.get("platform", "Engine")
        
        return {
            "type": "agent_post",
            "agent_name": action.get("agent_name", "AI Agent"),
            "agent_type": f"{platform.capitalize()} {agent_role}", 
            "content": content or f"Action: {action.get('action_type')}",
            "timestamp": action.get("timestamp", datetime.now().isoformat()),
            "progress": progress,
            "mode": "live"
        }


    async def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        """Fetch graph data (nodes and edges) from MiroFish engine."""
        try:
            resp = await self._request("GET", f"/graph/data/{graph_id}")
            return resp.get("data") or {}
        except Exception as e:
            logger.error(f"Failed to fetch graph data for {graph_id}: {e}")
            return {}

    async def generate_report(self, simulation_id: str, force_regenerate: bool = False) -> Dict[str, Any]:
        """Trigger ReportAgent to generate a Markdown report for this simulation."""
        logger.info(f"Triggering MiroFish report generation for simulation {simulation_id}...")
        return await self._request("POST", "/api/report/generate", json={
            "simulation_id": simulation_id,
            "force_regenerate": force_regenerate
        })

    async def get_report_status(self, task_id: str, simulation_id: Optional[str] = None) -> Dict[str, Any]:
        """Get report generation task progress status."""
        payload = {"task_id": task_id}
        if simulation_id:
            payload["simulation_id"] = simulation_id
        return await self._request("POST", "/api/report/generate/status", json=payload)

    async def get_report_by_simulation(self, simulation_id: str) -> Dict[str, Any]:
        """Fetch completed simulation report markdown."""
        return await self._request("GET", f"/api/report/by-simulation/{simulation_id}")

