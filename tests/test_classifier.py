"""Tests for classifier/rules.py — rule-based job classification."""

from classifier.rules import classify_job, CATEGORIES


class TestClassifyJob:
    def test_rag_job(self):
        cat, conf = classify_job(
            title="Build RAG Pipeline with Pinecone",
            description="We need a retrieval augmented generation system for our docs.",
            skills=["Python", "LangChain", "Pinecone"],
        )
        assert cat == "rag_doc_ai"
        assert 0.0 < conf <= 1.0

    def test_chatbot_job(self):
        cat, conf = classify_job(
            title="AI Chatbot for Customer Support",
            description="Build a conversational AI assistant using Dialogflow.",
            skills=["Dialogflow", "Python", "NLP"],
        )
        assert cat == "ai_chatbot"

    def test_agent_job(self):
        cat, conf = classify_job(
            title="Build Multi-Agent AI System with CrewAI",
            description="Need autonomous AI agents for sales outreach.",
            skills=["CrewAI", "LangGraph", "Python"],
        )
        assert cat == "ai_agent"

    def test_web_scraping_classified_as_automation(self):
        cat, conf = classify_job(
            title="Web Scraping Expert Needed",
            description="Scrape product data from e-commerce sites using Selenium.",
            skills=["Python", "Selenium", "BeautifulSoup"],
        )
        assert cat == "automation"

    def test_computer_vision_job(self):
        cat, conf = classify_job(
            title="Object Detection with YOLO",
            description="Need computer vision expert for real-time object detection.",
            skills=["Python", "OpenCV", "YOLO", "PyTorch"],
        )
        assert cat == "computer_vision"

    def test_vague_job_returns_other(self):
        cat, conf = classify_job(
            title="Help with project",
            description="Need some technical help.",
            skills=[],
        )
        assert cat == "other"
        assert conf <= 0.5

    def test_none_inputs_dont_crash(self):
        cat, conf = classify_job(title=None, description=None, skills=None)
        assert isinstance(cat, str)
        assert isinstance(conf, float)

    def test_empty_inputs_dont_crash(self):
        cat, conf = classify_job(title="", description="", skills=[])
        assert cat == "other"

    def test_confidence_range(self):
        cat, conf = classify_job(
            title="Fine-tune LLM model",
            description="Fine-tuning GPT model on custom dataset with PyTorch.",
            skills=["PyTorch", "Hugging Face"],
        )
        assert 0.0 <= conf <= 1.0

    def test_all_categories_are_valid_keys(self):
        """Every category returned should exist in CATEGORIES dict."""
        test_cases = [
            ("Build React + AI SaaS MVP", "Full stack AI web app", ["React", "OpenAI", "Node.js"]),
            ("Voice AI Agent with Vapi", "Build voice bot", ["Vapi", "ElevenLabs"]),
            ("Data Pipeline ETL", "Build data pipeline with Airflow", ["Airflow", "Python"]),
        ]
        for title, desc, skills in test_cases:
            cat, _ = classify_job(title, desc, skills)
            assert cat in CATEGORIES, f"Unknown category '{cat}' for job: {title}"
