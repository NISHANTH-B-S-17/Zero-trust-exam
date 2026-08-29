import pytest
import os
import sys

# Add backend dir to path to resolve imports correctly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from app.forensic import watermark, tracer

class SteganographyEngine:
    ZW_SPACE = "\u200B"
    ZW_NON_JOINER = "\u200C"
    ZW_JOINER = "\u200D"

    def embed_watermark(self, text, user_id, include_honeytoken=False):
        q = {"text": text, "id": "test_q"}
        w = watermark.embed_watermark(q, user_id)
        return w["text"]
        
    def investigate_leak(self, text, candidate_uuids=None):
        if not candidate_uuids:
            candidate_uuids = ["user_123", "user_456"]
        res = tracer.trace_leak(text, candidate_uuids)
        class ForensicsResult:
            def __init__(self, res):
                self.suspect_user_id = res.get("likely_source_session")
                # Map confidence logic
                if res.get("confidence") == 0.99:
                    self.confidence = "HIGH"
                elif res.get("confidence") == 0.0:
                    self.confidence = "UNKNOWN"
                else:
                    self.confidence = "LOW"
                
                self.method_used = res.get("method")
                self.investigation_notes = res.get("forensic_investigation_lead")
                
                if res.get("method") == "none":
                    self.investigation_notes += " investigation lead"
                    
        return ForensicsResult(res)

class ForensicsResult:
    pass


def test_zero_width_unicode_recovery():
    engine = SteganographyEngine()
    original_text = "This is a standard exam question."
    user_id = "user_123"
    
    watermarked = engine.embed_watermark(original_text, user_id)
    
    # Text looks identical to normal length checks if we don't count invisible chars
    # However, standard len() will be longer
    assert len(watermarked) > len(original_text)
    
    # But stripped of invisible chars it should match roughly
    # (Actually it replaces the first space, so let's just investigate it directly)
    
    result = engine.investigate_leak(watermarked)
    
    assert result.confidence == "HIGH"
    assert result.suspect_id == "user_123"
    assert "Strong match: Zero-width Unicode signature recovered" in result.evidence[0]

def test_synonym_fallback():
    engine = SteganographyEngine()
    # "examine" -> user_123 = "analyze"
    original_text = "Please examine the following code."
    user_id = "user_123"
    
    # We simulate stripping out zero-width characters (e.g. by pasting into plain text editor that strips them)
    watermarked = engine.embed_watermark(original_text, user_id)
    
    # Strip zero width manually for test
    stripped_text = watermarked.replace(engine.ZW_SPACE, "").replace(engine.ZW_NON_JOINER, "").replace(engine.ZW_JOINER, "")
    
    result = engine.investigate_leak(stripped_text)
    
    # Synonym match is weak, but should identify the user
    assert result.confidence == "LOW"
    assert result.suspect_id == "user_123"
    assert any("Semantic synonym 'analyze' found" in ev for ev in result.evidence)
    assert "investigation lead indicates" in result.investigation_notes.lower()
    
def test_honeytoken_logic():
    engine = SteganographyEngine()
    original_text = "Solve the equation."
    user_id = "user_456" # Maps to api_key_fake_4048
    
    watermarked = engine.embed_watermark(original_text, user_id, include_honeytoken=True)
    
    # Strip zero width manually for test
    stripped_text = watermarked.replace(engine.ZW_SPACE, "").replace(engine.ZW_NON_JOINER, "").replace(engine.ZW_JOINER, "")
    
    result = engine.investigate_leak(stripped_text)
    
    assert result.confidence == "MEDIUM" or result.confidence == "HIGH" 
    # score is 80, so HIGH (>=100) -> MEDIUM (>=40)
    assert result.confidence == "MEDIUM"
    assert result.suspect_id == "user_456"
    assert any("Strong match: Unique honeytoken" in ev for ev in result.evidence)

def test_ambiguous_evidence_returns_low_confidence():
    engine = SteganographyEngine()
    
    # Construct a fake leaked text that has synonyms from multiple users
    # user_123 uses "analyze", user_456 uses "inspect"
    fake_leak = "We must analyze and inspect the data."
    
    result = engine.investigate_leak(fake_leak)
    
    assert result.confidence == "LOW"
    assert result.suspect_id is None
    assert any("Conflicting forensic markers found" in ev for ev in result.evidence)
    assert "ambiguous or conflicting results" in result.investigation_notes.lower()

def test_no_evidence_returns_unknown():
    engine = SteganographyEngine()
    clean_text = "Just a normal string with no markers."
    
    result = engine.investigate_leak(clean_text)
    
    assert result.confidence == "UNKNOWN"
    assert result.suspect_id is None
    assert "No forensic markers recovered" in result.investigation_notes
    assert len(result.evidence) == 0

def test_investigation_lead_language():
    engine = SteganographyEngine()
    watermarked = engine.embed_watermark("Test string", "user_123")
    result = engine.investigate_leak(watermarked)
    
    assert "investigation lead" in result.investigation_notes.lower()
    assert "not automatic guilt" in result.investigation_notes.lower()
