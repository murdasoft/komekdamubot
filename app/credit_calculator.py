"""
Credit calculator for Komek Damu Bot.
Calculates monthly payments and total interest.
"""

from typing import Dict, Optional


def calculate_loan(
    amount: float,
    rate: float,
    years: int,
) -> Dict[str, float]:
    """
    Calculate loan details.
    
    Args:
        amount: Loan amount in tenge
        rate: Annual interest rate (e.g., 12.6 for 12.6%)
        years: Loan term in years
    
    Returns:
        Dict with monthly_payment, total_payment, total_interest
    """
    monthly_rate = rate / 100 / 12
    months = years * 12
    
    if monthly_rate == 0:
        monthly_payment = amount / months
    else:
        monthly_payment = amount * (monthly_rate * (1 + monthly_rate) ** months) / ((1 + monthly_rate) ** months - 1)
    
    total_payment = monthly_payment * months
    total_interest = total_payment - amount
    
    return {
        "monthly_payment": round(monthly_payment, 2),
        "total_payment": round(total_payment, 2),
        "total_interest": round(total_interest, 2),
        "amount": amount,
        "rate": rate,
        "years": years,
    }


def format_calculation_result(calc: Dict, lang: str = "ru") -> str:
    """Format calculation result for display."""
    if lang == "kk":
        return (
            f"💰 *Несие есептеу*\n\n"
            f"Сома: {calc['amount']:,.0f} теңге\n"
            f"Мөлшерлеме: {calc['rate']}% жылына\n"
            f"Мерзім: {calc['years']} жыл\n\n"
            f"Айлық төлем: {calc['monthly_payment']:,.0f} теңге\n"
            f"Жалпы төлем: {calc['total_payment']:,.0f} теңге\n"
            f"Пайыз: {calc['total_interest']:,.0f} теңге"
        )
    return (
        f"💰 *Расчёт кредита*\n\n"
        f"Сумма: {calc['amount']:,.0f} тенге\n"
        f"Ставка: {calc['rate']}% годовых\n"
        f"Срок: {calc['years']} лет\n\n"
        f"Ежемесячный платёж: {calc['monthly_payment']:,.0f} тенге\n"
        f"Общая выплата: {calc['total_payment']:,.0f} тенге\n"
        f"Переплата: {calc['total_interest']:,.0f} тенге"
    )


def extract_amount_and_rate(text: str) -> Optional[Dict[str, float]]:
    """
    Extract loan amount and rate from text.
    Returns None if not found.
    """
    import re
    
    # Extract amount (numbers with possible spaces, commas, dots)
    amount_match = re.search(r'(\d[\d\s,.]*\d)', text.replace(',', ''))
    if not amount_match:
        return None
    
    amount_str = amount_match.group(1).replace(' ', '').replace(',', '')
    try:
        amount = float(amount_str)
    except:
        return None
    
    # Extract rate
    rate = None
    rate_match = re.search(r'(\d+\.?\d*)\s*%?', text)
    if rate_match:
        rate = float(rate_match.group(1))
    else:
        # Default rates based on context
        if "даму" in text.lower() or "damu" in text.lower():
            rate = 12.6
        elif "ипотека" in text.lower() or "ипотек" in text.lower():
            rate = 18.0  # Default mortgage rate
        else:
            rate = 21.0  # Default business credit rate
    
    # Extract years
    years = None
    years_match = re.search(r'(\d+)\s*(лет|год|жыл)', text.lower())
    if years_match:
        years = int(years_match.group(1))
    else:
        years = 10 if ("даму" in text.lower() or "damu" in text.lower()) else 5
    
    return {
        "amount": amount,
        "rate": rate,
        "years": years,
    }
