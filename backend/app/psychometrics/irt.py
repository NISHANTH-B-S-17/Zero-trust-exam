import math

def calculate_probability(theta: float, a: float, b: float, c: float) -> float:
    """
    3PL IRT formula:
    P(theta) = c + (1-c) / (1 + exp(-a * (theta - b)))
    
    theta: student ability
    a: discrimination
    b: difficulty
    c: guessing
    """
    try:
        exponent = -a * (theta - b)
        # Prevent math domain errors on extreme values
        if exponent > 500:
            return c
        elif exponent < -500:
            return 1.0
        
        return c + (1 - c) / (1 + math.exp(exponent))
    except OverflowError:
        return c if (theta - b) < 0 else 1.0
