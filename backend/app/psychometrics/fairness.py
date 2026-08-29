import statistics
from typing import List, Dict, Any

class FormEquivalenceValidator:
    @staticmethod
    def calculate_stats(form: List[Dict[str, Any]]) -> Dict[str, Any]:
        difficulties = [q.get('irt_difficulty', 0) for q in form]
        marks = [q.get('marks', 1) for q in form]
        times = [q.get('estimated_time_seconds', 60) for q in form]
        
        return {
            "count": len(form),
            "total_marks": sum(marks),
            "total_time": sum(times),
            "mean_difficulty": statistics.mean(difficulties) if difficulties else 0,
            "stddev_difficulty": statistics.stdev(difficulties) if len(difficulties) > 1 else 0
        }

    @staticmethod
    def validate_equivalence(form_a: List[Dict[str, Any]], form_b: List[Dict[str, Any]], tolerance: float = 0.05) -> Dict[str, Any]:
        """Validates if two generated forms are fair and equivalent."""
        stats_a = FormEquivalenceValidator.calculate_stats(form_a)
        stats_b = FormEquivalenceValidator.calculate_stats(form_b)
        
        is_fair = True
        reasons = []
        
        if stats_a["count"] != stats_b["count"]:
            is_fair = False
            reasons.append("Question counts mismatch")
            
        if stats_a["total_marks"] != stats_b["total_marks"]:
            is_fair = False
            reasons.append("Total marks mismatch")
            
        if stats_a["total_time"] != stats_b["total_time"]:
            is_fair = False
            reasons.append("Total time mismatch")
            
        mean_diff = abs(stats_a["mean_difficulty"] - stats_b["mean_difficulty"])
        if mean_diff > tolerance:
            is_fair = False
            reasons.append(f"Mean difficulty difference ({mean_diff:.3f}) exceeds tolerance ({tolerance})")
            
        return {
            "is_fair": is_fair,
            "form_a_stats": stats_a,
            "form_b_stats": stats_b,
            "reasons": reasons
        }
