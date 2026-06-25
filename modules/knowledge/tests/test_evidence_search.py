import importlib
import sys
import json
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def _load_search_service():
    for module_name, module in sys.modules.items():
        if module_name.endswith(".search_service") and hasattr(module, "build_evidence_packet_sync"):
            return module
    return importlib.import_module("modules.knowledge.backend.services.search_service")


class TestEvidencePacketBuilder:

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.svc = _load_search_service()
        self.AnswerabilityJudgment = self.svc.AnswerabilityJudgment
        self.QueryRewriteResult = self.svc.QueryRewriteResult
        self.EvidencePacket = self.svc.EvidencePacket
        self.EvidenceCitation = self.svc.EvidenceCitation

    def test_build_empty_results(self):
        judgment = self.AnswerabilityJudgment("no", "no results", 0.0)
        packet = self.svc.build_evidence_packet_sync("test query", [], judgment)
        assert packet.answerable == "no"
        assert packet.citation_count == 0
        assert packet.citations == []

    def test_build_with_citations(self):
        results = [
            {"chunk_id": 1, "document_id": 10, "page": 1, "text": "hello world", "rrf_score": 0.85, "source": "vector", "document_name": "doc1.pdf"},
            {"chunk_id": 2, "document_id": 10, "page": 2, "text": "second chunk", "rrf_score": 0.72, "source": "keyword", "document_name": "doc1.pdf"},
        ]
        judgment = self.AnswerabilityJudgment("yes", "good results", 0.9)
        packet = self.svc.build_evidence_packet_sync("test", results, judgment)
        assert packet.answerable == "yes"
        assert packet.citation_count == 2
        assert packet.citations[0].document_id == 10
        assert packet.citations[1].source == "keyword"

    def test_build_with_rewrite(self):
        results = [{"chunk_id": 1, "document_id": 10, "text": "test", "rrf_score": 0.5, "source": "vector", "document_name": "doc.pdf"}]
        judgment = self.AnswerabilityJudgment("weak", "partial", 0.5)
        rewrite = self.QueryRewriteResult("original query", "rewritten query", False, 0.8, "expanded")
        packet = self.svc.build_evidence_packet_sync("original query", results, judgment, rewrite=rewrite)
        assert packet.rewritten_query == "rewritten query"
        assert packet.answerable == "weak"

    def test_build_with_fusion_graph_context(self):
        results = [{"chunk_id": 1, "document_id": 10, "text": "test", "rrf_score": 0.6, "source": "vector", "document_name": "doc.pdf"}]
        judgment = self.AnswerabilityJudgment("yes", "ok", 0.8)
        fusion_ctx = [{"page": 1, "page_summary": "test summary"}]
        graph_ctx = [{"entity": "test", "relation": "related"}]
        packet = self.svc.build_evidence_packet_sync("q", results, judgment, fusion_context=fusion_ctx, graph_context=graph_ctx)
        assert len(packet.fusion_context) == 1
        assert len(packet.graph_context) == 1
        assert packet.fusion_context[0]["page_summary"] == "test summary"

    def test_citation_provenance(self):
        results = [
            {"chunk_id": 1, "document_id": 10, "text": "chunk with doc name", "rrf_score": 0.9, "source": "vector", "document_name": "年度报告.pdf"},
        ]
        judgment = self.AnswerabilityJudgment("yes", "high confidence", 0.95)
        packet = self.svc.build_evidence_packet_sync("query", results, judgment)
        assert packet.citations[0].provenance == "年度报告.pdf"

    def test_serializable(self):
        results = [{"chunk_id": 1, "document_id": 10, "text": "test", "rrf_score": 0.5, "source": "vector", "document_name": "doc.pdf"}]
        judgment = self.AnswerabilityJudgment("yes", "ok", 0.8)
        packet = self.svc.build_evidence_packet_sync("q", results, judgment)
        d = {
            "answerable": packet.answerable,
            "answerability_reason": packet.answerability_reason,
            "citation_count": packet.citation_count,
        }
        dumped = json.dumps(d)
        loaded = json.loads(dumped)
        assert loaded["answerable"] == "yes"
        assert loaded["citation_count"] == 1
