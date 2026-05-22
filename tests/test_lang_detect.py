from app.bot.lang_detect import detect_message_lang


def test_russian_credit_message():
    assert detect_message_lang("здравствуйте взять хочу кредит на 1 000 000") == "ru"


def test_kazakh_with_special_chars():
    assert detect_message_lang("Сәлем, несие керек") == "kk"


def test_russian_credit_word_alone():
    assert detect_message_lang("нужен кредит") == "ru"
