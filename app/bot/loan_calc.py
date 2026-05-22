"""Loan payment calculator (shared by handlers and FAQ matcher)."""


def calculate_loan_payment(amount: float, rate: float, years: int) -> tuple[float, float]:
    monthly_rate = rate / 100 / 12
    months = years * 12
    if monthly_rate == 0:
        monthly = amount / months
    else:
        monthly = amount * (monthly_rate * (1 + monthly_rate) ** months) / (
            (1 + monthly_rate) ** months - 1
        )
    total = monthly * months
    return round(monthly, 0), round(total, 0)


def format_calculator_result(params: dict, lang: str = "ru") -> str:
    amount = params["amount"]
    rate = params["rate"]
    years = params["years"]
    monthly, total = calculate_loan_payment(amount, rate, years)
    overpay = total - amount
    amount_str = f"{amount:,.0f}".replace(",", " ")
    monthly_str = f"{monthly:,.0f}".replace(",", " ")
    total_str = f"{total:,.0f}".replace(",", " ")
    overpay_str = f"{overpay:,.0f}".replace(",", " ")

    if lang == "kk":
        return (
            f"Шамамен ай сайын: ~{monthly_str} ₸ ({rate}%, {years} жыл).\n"
            f"Нақты есеп — офисте."
        )
    return (
        f"Примерно в месяц: ~{monthly_str} ₸ ({rate}%, {years} лет).\n"
        f"Точный расчёт — в офисе."
    )
