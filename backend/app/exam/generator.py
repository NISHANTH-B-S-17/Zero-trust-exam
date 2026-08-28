import hashlib
import random
from typing import List, Dict, Any

class FairExamFormGenerator:
    @staticmethod
    def generate_deterministic_paper(questions: List[Dict[str, Any]], student_uuid: str, target_count: int = 10) -> List[Dict[str, Any]]:
        if not questions:
            return []
            
        target_count = min(target_count, len(questions))
        
        # Group by topic to ensure distribution
        topics = {}
        for q in questions:
            topic = q.get('topic', 'general')
            if topic not in topics:
                topics[topic] = []
            topics[topic].append(q)
            
        # Deterministic sort
        for topic in topics:
            topics[topic] = sorted(topics[topic], key=lambda x: str(x.get('id', 0)))
            
        seed = int(hashlib.md5(student_uuid.encode()).hexdigest(), 16)
        rng = random.Random(seed)
        
        selected = []
        topic_keys = sorted(list(topics.keys()))
        
        if not topic_keys:
            return []
            
        idx = 0
        while len(selected) < target_count:
            current_topic = topic_keys[idx % len(topic_keys)]
            available = topics[current_topic]
            
            if available:
                q_idx = rng.randrange(len(available))
                selected.append(available.pop(q_idx))
                
            idx += 1
            if all(len(t) == 0 for t in topics.values()):
                break
                
        rng.shuffle(selected)
        return selected
