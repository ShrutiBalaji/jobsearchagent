"""Optional LLM-enhanced scoring (gracefully disabled without API key)."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from job_agent.config import AppConfig
from job_agent.models import JobRecord

if TYPE_CHECKING:
    pass

logger = logging.getLogger("job_agent.llm_scorer")

CANDIDATE_PROFILE = """
Shruti Balaji — AI Engineer with ~5 years of AI/ML experience across multiple industries.
MS Data Science (UMass Dartmouth). Mid-level candidate, NOT a new grad or 1-year engineer.

Experience timeline:
- AI Engineer, Saince Inc (Oct 2025–present): production medical imaging AI platform,
  3-server distributed inference pipeline, DICOM ingestion through reporting
- AI Engineer, ARMA AI Labs (Jul–Sep 2025): LLM fine-tuning (LoRA/PEFT) for TTS/audio,
  billion-parameter models, CUDA/PyTorch
- Researcher, Multi-scale Medical Robotics Lab / UMassD (Oct 2023–May 2025): Faster R-CNN
  for breast cancer detection on DICOM mammograms, 92% precision
- ML Engineer Intern, SASTRA University (Feb 2021–Feb 2023): CNN/ResNet50 on DICOM,
  Random Forest compound screening, HPC on 64-core cluster

Industries: healthcare/medical imaging, audio/LLM, fintech streaming, offshore wind
analytics, academic research.

Core skills: Python, PyTorch, TensorFlow, CUDA, Hugging Face, LangChain, RAG, LoRA/PEFT,
computer vision (Faster R-CNN, YOLO, ResNet), DICOM, Kafka, AWS (SageMaker, Glue, Athena),
Docker, Django, FastAPI, distributed systems, agentic AI (LangChain, AutoGen, CrewAI).

Target level: mid-level AI/ML engineer — strong fit for 3–7 year roles. Do not treat
as underqualified for standard ML Engineer or AI Engineer roles.
"""


class LLMScorer:
    """Optional LLM second-pass for nuanced fit analysis."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.enabled = bool(config.llm_provider and config.llm_api_key)

    def enhance(self, job: JobRecord) -> JobRecord:
        """Enhance job with LLM analysis if enabled."""
        if not self.enabled:
            return job

        try:
            analysis = self._call_llm(job)
            if analysis:
                if analysis.get("why_match"):
                    job.why_match = analysis["why_match"]
                if analysis.get("missing_requirements"):
                    job.missing_requirements = analysis["missing_requirements"]
                if analysis.get("risk_flags"):
                    job.risk_flags.extend(analysis["risk_flags"])
        except Exception as exc:
            logger.warning("LLM scoring failed for %s: %s", job.title, exc)

        return job

    def _call_llm(self, job: JobRecord) -> dict | None:
        provider = (self.config.llm_provider or "").lower()

        prompt = f"""Analyze job fit for candidate. Return JSON with keys:
why_match (string), missing_requirements (string), risk_flags (list of strings).
Do NOT change match score. Candidate: {CANDIDATE_PROFILE}
Job: {job.title} at {job.company}
Description: {job.description[:3000]}
"""

        if provider == "openai":
            return self._call_openai(prompt)
        logger.warning("Unknown LLM provider: %s", provider)
        return None

    def _call_openai(self, prompt: str) -> dict | None:
        import requests

        model = self.config.llm_model or "gpt-4o-mini"
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.config.llm_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
            },
            timeout=30,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(content)
