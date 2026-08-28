import re
import uuid
import base64
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

@dataclass
class ForensicsResult:
    confidence: str # "HIGH", "MEDIUM", "LOW", "UNKNOWN"
    suspect_id: Optional[str]
    evidence: List[str]
    investigation_notes: str

class SteganographyEngine:
    """
    Implements a tri-layer forensic leak tracing engine:
    1. Zero-width Unicode characters (invisible to humans, persists copy-paste)
    2. Synonym substitution (semantic watermarking)
    3. Honeytokens (fake identifiable data)
    """
    
    # Zero-width characters for binary encoding
    ZW_SPACE = '\u200B' # represents '0'
    ZW_NON_JOINER = '\u200C' # represents '1'
    ZW_JOINER = '\u200D' # delimiter
    
    # Simple synonym map for semantic watermarking
    # Format: {original_word: {user_id: assigned_synonym}}
    # In a real app, this would be dynamically generated or from a DB
    SYNONYM_MAP = {
        "examine": {
            "user_123": "analyze",
            "user_456": "inspect",
            "user_789": "evaluate"
        },
        "significant": {
            "user_123": "substantial",
            "user_456": "notable",
            "user_789": "important"
        }
    }
    
    # Honeytokens mapped to user IDs
    HONEYTOKENS = {
        "project_omega_reference_99": "user_123",
        "api_key_fake_4048": "user_456",
        "john.doe+test@example.com": "user_789"
    }

    def __init__(self):
        # We need a reverse map for fast lookups
        self.reverse_synonyms = {}
        for original, user_mapping in self.SYNONYM_MAP.items():
            for uid, synonym in user_mapping.items():
                self.reverse_synonyms[synonym.lower()] = uid

    def _text_to_binary(self, text: str) -> str:
        return ''.join(format(ord(c), '08b') for c in text)

    def _binary_to_text(self, binary: str) -> str:
        try:
            return ''.join(chr(int(binary[i:i+8], 2)) for i in range(0, len(binary), 8))
        except ValueError:
            return ""

    def _binary_to_zw(self, binary: str) -> str:
        zw_str = ""
        for bit in binary:
            if bit == '0':
                zw_str += self.ZW_SPACE
            elif bit == '1':
                zw_str += self.ZW_NON_JOINER
        return zw_str + self.ZW_JOINER

    def _zw_to_binary(self, text: str) -> str:
        binary = ""
        for char in text:
            if char == self.ZW_SPACE:
                binary += '0'
            elif char == self.ZW_NON_JOINER:
                binary += '1'
            elif char == self.ZW_JOINER:
                break
        return binary

    def embed_watermark(self, paper_text: str, user_id: str, include_honeytoken: bool = False) -> str:
        """
        Embeds a tri-layer watermark into the text for a specific user.
        """
        watermarked_text = paper_text
        
        # Layer 1: Synonym Substitution
        # Only replace whole words (very simplified regex)
        for original, mappings in self.SYNONYM_MAP.items():
            if user_id in mappings:
                synonym = mappings[user_id]
                # Replace original with synonym (case insensitive match, keeps synonym lowercase for simplicity)
                watermarked_text = re.sub(r'\b' + re.escape(original) + r'\b', synonym, watermarked_text, flags=re.IGNORECASE)

        # Layer 2: Honeytoken insertion
        # Find if there is a honeytoken for this user
        if include_honeytoken:
            for token, uid in self.HONEYTOKENS.items():
                if uid == user_id:
                    # Append it subtly at the end or in a comment
                    watermarked_text += f"\n<!-- ref: {token} -->"
                    break

        # Layer 3: Zero-width Unicode encoding
        # Embed the user ID as binary using zero-width characters at the end of the first paragraph or string
        binary_id = self._text_to_binary(user_id)
        zw_signature = self._binary_to_zw(binary_id)
        
        # Insert signature after first space or at end if no spaces
        space_idx = watermarked_text.find(' ')
        if space_idx != -1:
            watermarked_text = watermarked_text[:space_idx] + zw_signature + watermarked_text[space_idx:]
        else:
            watermarked_text += zw_signature

        return watermarked_text

    def investigate_leak(self, recovered_text: str) -> ForensicsResult:
        """
        Analyzes leaked text to determine the source.
        Returns a ForensicsResult acting as an investigation lead.
        """
        evidence_log = []
        suspects_scores = {} # user_id: score
        
        def add_score(uid: str, points: int, reason: str):
            suspects_scores[uid] = suspects_scores.get(uid, 0) + points
            evidence_log.append(reason)

        # 1. Check Zero-width signature
        binary_sig = self._zw_to_binary(recovered_text)
        if binary_sig:
            decoded_uid = self._binary_to_text(binary_sig)
            # Basic validation that it looks like a user ID (printable chars)
            if decoded_uid and decoded_uid.isprintable():
                add_score(decoded_uid, 100, f"Strong match: Zero-width Unicode signature recovered pointing to {decoded_uid}.")
            else:
                 evidence_log.append("Notice: Zero-width characters found but payload is corrupted/unreadable.")
        
        # 2. Check Honeytokens
        for token, uid in self.HONEYTOKENS.items():
            if token in recovered_text:
                add_score(uid, 80, f"Strong match: Unique honeytoken '{token}' found in text.")

        # 3. Check Synonyms
        words = re.findall(r'\b\w+\b', recovered_text.lower())
        synonym_matches = 0
        for word in words:
            if word in self.reverse_synonyms:
                uid = self.reverse_synonyms[word]
                add_score(uid, 20, f"Weak match: Semantic synonym '{word}' found.")
                synonym_matches += 1

        if not suspects_scores:
            return ForensicsResult(
                confidence="UNKNOWN",
                suspect_id=None,
                evidence=evidence_log,
                investigation_notes="No forensic markers recovered from the provided text. The leak source cannot be determined."
            )

        # Determine primary suspect
        primary_suspect = max(suspects_scores, key=suspects_scores.get)
        max_score = suspects_scores[primary_suspect]

        # Determine confidence
        confidence = "LOW"
        if max_score >= 100:
            confidence = "HIGH"
        elif max_score >= 40:
            confidence = "MEDIUM"

        # Check for ambiguity (e.g. conflicting signals)
        # If the second highest score is close to the highest, lower confidence
        if len(suspects_scores) > 1:
            sorted_scores = sorted(suspects_scores.values(), reverse=True)
            if sorted_scores[0] - sorted_scores[1] < 30:
                confidence = "LOW"
                evidence_log.append("Warning: Conflicting forensic markers found. Multiple user traces detected.")
                primary_suspect = None # Ambiguous

        notes = (
            f"Investigation lead indicates a potential link to user {primary_suspect} based on {len(evidence_log)} evidence markers. "
            "This is a directional finding, not automatic guilt. Further contextual verification (e.g., access logs, risk events) is required."
        ) if primary_suspect else "Investigation yielded ambiguous or conflicting results. No single suspect can be confidently identified."

        return ForensicsResult(
            confidence=confidence,
            suspect_id=primary_suspect,
            evidence=evidence_log,
            investigation_notes=notes
        )
