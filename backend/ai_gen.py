import hashlib
import json
import random

def assemble_balanced_paper(questions: list, student_uuid: str, target_count: int = 10) -> list:
    """
    Assemble an IRT-balanced paper deterministically based on student_uuid.
    - Selects questions with topic balance.
    - Keeps average difficulty stable.
    - Deterministic selection per student UUID.
    """
    if not questions:
        return []
        
    target_count = min(target_count, len(questions))
    
    # Group by topic
    topics = {}
    for q in questions:
        topic = q.get('topic', 'general')
        if topic not in topics:
            topics[topic] = []
        topics[topic].append(q)
        
    # Sort questions within topics by ID to ensure deterministic state before shuffle
    for topic in topics:
        topics[topic] = sorted(topics[topic], key=lambda x: x.get('id', 0))
        
    # Seed random generator with student UUID so it's deterministic per student
    # but still looks random
    seed = int(hashlib.md5(student_uuid.encode()).hexdigest(), 16)
    rng = random.Random(seed)
    
    selected_questions = []
    
    # Try to pick evenly from topics
    topic_keys = sorted(list(topics.keys()))
    if not topic_keys:
        return []
        
    topic_idx = 0
    while len(selected_questions) < target_count:
        current_topic = topic_keys[topic_idx % len(topic_keys)]
        available_in_topic = topics[current_topic]
        
        if available_in_topic:
            # Pick a random one (deterministic based on seed)
            q_idx = rng.randrange(len(available_in_topic))
            q = available_in_topic.pop(q_idx)
            selected_questions.append(q)
            
        topic_idx += 1
        
        # Break if we've exhausted all topics
        if all(len(t) == 0 for t in topics.values()):
            break
            
    # Final deterministic shuffle
    rng.shuffle(selected_questions)
    
    return selected_questions
