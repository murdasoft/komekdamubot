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
            f"💰 Кредит сомасы: {amount_str} ₸\n"
            f"📊 Мерзімі: {years} жыл\n"
            f"📈 Пайыздық мөлшерлеме: {rate}%\n\n"
            f"💳 Ай сайынғы төлем: {monthly_str} ₸\n"
            f"📝 Жалпы төлем: {total_str} ₸\n"
            f"⚠️ Асылып кету: {overpay_str} ₸\n\n"
            f"Толық есептеу үшін офиске келіңіз!"
        )
    return (
        f"💰 Сумма кредита: {amount_str} ₸\n"
        f"📊 Срок: {years} лет\n"
        f"📈 Процентная ставка: {rate}%\n\n"
        f"💳 Ежемесячный платёж: {monthly_str} ₸\n"
        f"📝 Общая сумма выплат: {total_str} ₸\n"
        f"⚠️ Переплата: {overpay_str} ₸\n\n"
        f"Для точного расчёта приходите в офис!"
    )
