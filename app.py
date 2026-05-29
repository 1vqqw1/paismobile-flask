from functools import wraps
from datetime import datetime, timedelta

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for

from services.models import CityBook, PaymentBook, Promo, SubscriberBook, Tariff, check_card

app = Flask(__name__)
app.config["SECRET_KEY"] = "paismobile-lab-secret-key"

users = SubscriberBook()
cities_book = CityBook()
payments = PaymentBook()

TARIFF_NUMBERS = {
    1: "vestnik",
    2: "serafim",
    3: "kheruvim",
    4: "arkhangel",
    5: "prestol",
    6: "nefilim",
}

CITY_TARIFF_NUMBERS = {
    "Москва": [1, 2, 3, 4, 5, 6],
    "Санкт-Петербург": [1, 2, 3, 4, 5, 6],
    "Казань": [1, 2, 3, 4, 5, 6],
    "Екатеринбург": [1, 2, 3, 4, 5, 6],
    "Новосибирск": [1, 2, 3, 4, 5, 6],
    "Краснодар": [1, 2, 3, 4, 5, 6],
    "Нижний Новгород": [1, 2, 3, 4, 5],
    "Ростов-на-Дону": [1, 2, 3, 4, 5],
    "Уфа": [1, 2, 4, 5, 6],
    "Самара": [1, 2, 4, 5, 6],
    "Сочи": [2, 3, 4, 5, 6],
    "Калининград": [1, 2, 4, 5],
    "Владивосток": [1, 2, 4, 5],
    "Красноярск": [1, 2, 4, 5],
    "Воронеж": [1, 2, 4, 5],
    "Волгоград": [1, 2, 4, 5],
    "Мурманск": [1, 2, 4],
    "Архангельск": [1, 2, 4],
    "Ярославль": [1, 2, 4],
    "Омск": [1, 2, 4],
}


def tariff_ids_for_city(city_name):
    all_ids = [TARIFF_NUMBERS[i] for i in sorted(TARIFF_NUMBERS)]
    numbers = CITY_TARIFF_NUMBERS.get(city_name)
    if not numbers:
        return all_ids
    result = []
    for number in numbers:
        result.append(TARIFF_NUMBERS[number])
    return result


def get_current_user():
    user_id = session.get("user_id")
    if user_id:
        return users.get(user_id)
    return None


@app.context_processor
def add_common_data():
    return {
        "current_user": get_current_user(),
        "city_names": cities_book.names(),
        "format_phone": format_phone,
        "format_russian_date": format_russian_date,
        "next_payment_date": next_payment_date,
        "format_balance": format_balance,
        "format_card_number": format_card_number,
    }


def login_required(page):
    @wraps(page)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Войдите в личный кабинет, чтобы открыть эту страницу.", "warning")
            return redirect(url_for("login", next=request.path))
        return page(*args, **kwargs)
    return wrapper


def get_int(value, default_value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default_value


def request_values():
    if request.is_json:
        data = request.get_json(silent=True)
        if data:
            return data
    return request.form


def answer_json(ok, message, extra=None, status=200):
    result = {
        "ok": ok,
        "message": message,
    }
    if extra:
        result.update(extra)
    return jsonify(result), status


def format_balance(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = 0
    text_number = str(number)
    parts = []
    while text_number:
        parts.insert(0, text_number[-3:])
        text_number = text_number[:-3]
    return ' '.join(parts) if parts else '0'


def format_card_number(value):
    digits = ""
    for ch in str(value or ""):
        if ch.isdigit():
            digits += ch
    digits = digits[:16]
    if not digits:
        return ""
    parts = []
    for i in range(0, len(digits), 4):
        parts.append(digits[i:i + 4])
    return ' '.join(parts)


def card_form_data(form, user=None, bad_field=""):
    data = {
        "card": form.get("card", ""),
        "holder": form.get("holder", ""),
        "expire": form.get("expire", ""),
        "cvv": form.get("cvv", ""),
        "phone": form.get("phone", user.phone if user else ""),
        "email": form.get("email", user.email if user else ""),
        "amount": form.get("amount", "500"),
    }
    if bad_field in data:
        data[bad_field] = ""
    return data


def validate_card_form(form):
    card = ""
    for ch in form.get("card", ""):
        if ch.isdigit():
            card += ch

    holder = form.get("holder", "").strip()
    expire = form.get("expire", "").replace(" ", "").strip()
    cvv = form.get("cvv", "").strip()

    if len(card) != 16 or not card.isdigit():
        return None, "Номер карты должен содержать ровно 16 цифр.", "card"
    if not holder:
        return None, "Введите имя владельца карты.", "holder"

    valid_expire = False
    if len(expire) == 5 and expire[2] == "/":
        month_text = expire[:2]
        year_text = expire[3:]
        if month_text.isdigit() and year_text.isdigit():
            month = int(month_text)
            year = 2000 + int(year_text)
            if 1 <= month <= 12:
                now = datetime.utcnow()
                if year > now.year or (year == now.year and month >= now.month):
                    valid_expire = True
                else:
                    return None, "Карта просрочена.", "expire"
    if not valid_expire:
        return None, "Срок действия карты должен быть в формате ММ/ГГ.", "expire"

    if len(cvv) != 3 or not cvv.isdigit():
        return None, "CVV должен содержать ровно 3 цифры.", "cvv"

    return {
        "number": card,
        "holder": holder,
        "expiry": expire,
        "cvv": cvv,
        "last4": card[-4:],
    }, "", ""


def format_phone(value):
    digits = ""
    for ch in str(value or ""):
        if ch.isdigit():
            digits += ch
    if len(digits) == 11 and digits[0] == "7":
        digits = digits[1:]
    if len(digits) > 10:
        digits = digits[-10:]
    if not digits:
        return ""
    result = "+7"
    if len(digits) > 0:
        result += " (" + digits[:3]
    if len(digits) >= 3:
        result += ")"
    if len(digits) > 3:
        result += " " + digits[3:6]
    if len(digits) > 6:
        result += "-" + digits[6:8]
    if len(digits) > 8:
        result += "-" + digits[8:10]
    return result


def constructor_price(minutes, internet, sms):
    return round(160 + minutes * 0.32 + internet * 5 + sms * 0.6)


def format_russian_date(value):
    months = [
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря"
    ]
    if not value:
        return ""
    if isinstance(value, str):
        parsed = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(value, fmt)
                break
            except ValueError:
                pass
        if not parsed:
            return ""
    else:
        parsed = value
    return str(parsed.day) + " " + months[parsed.month - 1] + " " + str(parsed.year)


def next_payment_date(value):
    if not value:
        return ""
    parsed = None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(str(value), fmt)
            break
        except ValueError:
            pass
    if not parsed:
        return ""
    month = parsed.month + 1
    year = parsed.year
    if month > 12:
        month = 1
        year += 1
    days = [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    day = parsed.day
    if day > days[month - 1]:
        day = days[month - 1]
    result = datetime(year, month, day) + timedelta(days=1)
    return format_russian_date(result)


@app.route("/")
def index():
    return render_template("index.html", tariffs=Tariff.get_featured())


@app.route("/tariffs")
def tariffs():
    minutes = get_int(request.args.get("minutes"), 500)
    internet = get_int(request.args.get("internet"), 20)
    sms = get_int(request.args.get("sms"), 100)
    user = get_current_user()
    city_name = request.args.get("city")
    if city_name:
        session["selected_city"] = city_name
    else:
        if user and user.city:
            city_name = user.city
        else:
            city_name = session.get("selected_city", "Москва")
    return render_template(
        "tariffs.html",
        tariffs=Tariff.get_all(),
        minutes=minutes,
        internet=internet,
        sms=sms,
        city_name=city_name,
        city_names=cities_book.names(),
        available_ids=tariff_ids_for_city(city_name),
        total_price=constructor_price(minutes, internet, sms),
    )


@app.route("/actions", methods=["GET", "POST"])
def actions():
    if request.method == "POST":
        promo_id = request.form.get("promo_id", "").strip()
        promo_code = request.form.get("promo", "").strip()

        if promo_id:
            user = get_current_user()
            if not user:
                flash("Войдите в личный кабинет, чтобы активировать акцию.", "warning")
                return redirect(url_for("login", next=url_for("actions")))
            ok, message = users.activate_promo(user.id, promo_id, request.form)
            if ok:
                flash(message, "success")
            else:
                flash(message, "error")
            return redirect(url_for("actions"))

        if promo_code:
            flash("Промокод принят. Скидка будет применена при следующей оплате.", "success")
        else:
            flash("Введите промокод.", "warning")
        return redirect(url_for("actions"))

    return render_template("actions.html", promos=Promo.get_all())


@app.route("/cities")
def cities():
    query = request.args.get("q", "")
    return render_template("cities.html", cities=cities_book.load(query), query=query)


@app.route("/select-city/<city>", methods=["GET", "PUT"])
def select_city(city):
    session["selected_city"] = city
    user = get_current_user()
    if user:
        form = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "birth_date": user.birth_date,
            "gender": user.gender,
            "phone": user.phone,
            "email": user.email,
            "city": city,
        }
        users.update_profile(user.id, form)
    message = "Выбран город: " + city + "."
    if request.method == "PUT":
        return answer_json(True, message, {"city": city})
    flash(message, "success")
    return redirect(request.referrer or url_for("cities"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_value = request.form.get("login", "")
        password = request.form.get("password", "")
        user = users.login(login_value, password)
        if user:
            session["user_id"] = user.id
            flash("Вы вошли в личный кабинет.", "success")
            return redirect(request.args.get("next") or url_for("my_tariff"))
        flash("Неверный телефон/email или пароль.", "error")
    return render_template("login.html", simple_header=True, back_text="На главную", back_url=url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    flash("Вы вышли из личного кабинета.", "success")
    return redirect(url_for("index"))


@app.route("/register", methods=["GET", "POST"])
def register():
    form_data = {}
    if request.method == "POST":
        form_data = request.form.to_dict()
        user, error = users.add(request.form)
        if error:
            flash(error, "error")
            if "Пароль" in error or "Пароли" in error:
                form_data["password"] = ""
                form_data["password_confirm"] = ""
            elif "Имя" in error:
                form_data["first_name"] = ""
            elif "Фамилия" in error:
                form_data["last_name"] = ""
            elif "Телефон" in error or "телефон" in error:
                form_data["phone"] = ""
            elif "email" in error or "Email" in error:
                form_data["email"] = ""
            elif "город" in error or "Город" in error:
                form_data["city"] = ""
        else:
            session["user_id"] = user.id
            flash("Аккаунт создан. Добро пожаловать в ПайсМобайл.", "success")
            next_url = request.args.get("next")
            if next_url:
                return redirect(next_url)
            return redirect(url_for("profile"))
    return render_template(
        "register.html",
        cities=cities_book.names(),
        form_data=form_data,
        simple_header=True,
        back_text="На главную",
        back_url=url_for("index"),
    )


@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        if email:
            flash("Инструкции по восстановлению отправлены, если email есть в базе.", "success")
            return redirect(url_for("login"))
        flash("Введите email.", "warning")
    return render_template("forgot.html", simple_header=True, back_text="До входа", back_url=url_for("login"))


@app.route("/payment/<tariff_id>", methods=["GET", "POST"])
@login_required
def payment(tariff_id):
    tariff = Tariff.get(tariff_id)
    if not tariff:
        return render_template("404.html", simple_header=True, back_text="На главную", back_url=url_for("index")), 404

    user = get_current_user()
    city_name = session.get("selected_city") or user.city or "Москва"
    if tariff.id not in tariff_ids_for_city(city_name):
        flash("Этот тариф недоступен в выбранном городе.", "warning")
        return redirect(url_for("tariffs", city=city_name))
    if request.method == "POST":
        card, error, bad_field = validate_card_form(request.form)
        if error:
            flash(error, "error")
            return render_template(
                "payment.html",
                tariff=tariff,
                form_data=card_form_data(request.form, user, bad_field),
                step_title="Оплата",
                simple_header=True,
                back_text="Назад к тарифам",
                back_url=url_for("tariffs"),
            )

        payments.add(
            "tariff",
            tariff.price,
            user.id,
            {
                "tariff_id": tariff.id,
                "phone": request.form.get("phone", ""),
                "email": request.form.get("email", ""),
                "card_last4": card["last4"],
            },
        )
        users.save_card(user.id, card)
        users.set_tariff(user.id, tariff.id)
        flash("Оплата прошла успешно. Тариф «" + tariff.name + "» подключён.", "success")
        return redirect(url_for("my_tariff"))

    return render_template(
        "payment.html",
        tariff=tariff,
        form_data=card_form_data({}, user),
        step_title="Оплата",
        simple_header=True,
        back_text="Назад к тарифам",
        back_url=url_for("tariffs"),
    )


@app.route("/topup", methods=["GET", "POST"])
@login_required
def topup():
    user = get_current_user()
    if request.method == "POST":
        amount = get_int(request.form.get("amount"), 0)
        if amount <= 0:
            flash("Введите сумму пополнения больше нуля.", "error")
            return render_template(
                "topup.html",
                user=user,
                form_data=card_form_data(request.form, user, "amount"),
                simple_header=True,
                back_text="Назад",
                back_url=url_for("my_tariff"),
            )
        card, error, bad_field = validate_card_form(request.form)
        if error:
            flash(error, "error")
            return render_template(
                "topup.html",
                user=user,
                form_data=card_form_data(request.form, user, bad_field),
                simple_header=True,
                back_text="Назад",
                back_url=url_for("my_tariff"),
            )
        payments.add(
            "topup",
            amount,
            user.id,
            {
                "phone": request.form.get("phone", ""),
                "email": request.form.get("email", ""),
                "card_last4": card["last4"],
            },
        )
        users.save_card(user.id, card)
        users.add_balance(user.id, amount)
        flash("Оплата прошла успешно. Баланс пополнен на " + str(amount) + " ₽.", "success")
        return redirect(url_for("my_tariff"))
    return render_template(
        "topup.html",
        user=user,
        form_data=card_form_data({}, user),
        simple_header=True,
        back_text="Назад",
        back_url=url_for("my_tariff"),
    )


@app.route("/profile", methods=["GET", "POST", "PUT"])
@login_required
def profile():
    user = get_current_user()
    if request.method in ("POST", "PUT"):
        form = request_values()
        user, error = users.update_profile(user.id, form)
        if error:
            if request.method == "PUT":
                return answer_json(False, error, status=400)
            flash(error, "error")
            return redirect(url_for("profile"))

        new_password = form.get("new_password", "")
        if new_password:
            ok, message = users.change_password(
                user.id,
                form.get("current_password", ""),
                new_password,
                form.get("password_confirm", ""),
            )
            if request.method == "PUT":
                if ok:
                    return answer_json(True, message)
                return answer_json(False, message, status=400)
            if ok:
                flash(message, "success")
            else:
                flash(message, "error")
                return redirect(url_for("profile"))
        else:
            if request.method == "PUT":
                return answer_json(True, "Настройки профиля сохранены.")
            flash("Настройки профиля сохранены.", "success")
        return redirect(url_for("profile"))

    tariff = None
    if user.active_tariff:
        tariff = Tariff.get(user.active_tariff)
    return render_template("profile.html", user=user, tariff=tariff, cities=cities_book.names())


@app.route("/save-card", methods=["POST", "PUT"])
@login_required
def save_card():
    user = get_current_user()
    form = request_values()
    card, error = check_card(form)
    if error:
        if request.method == "PUT":
            return answer_json(False, error, status=400)
        flash(error, "error")
    else:
        users.save_card(user.id, card)
        if request.method == "PUT":
            return answer_json(True, "Карта сохранена.", {"last4": card.get("last4", "")})
        flash("Карта сохранена.", "success")
    return redirect(url_for("profile"))


@app.route("/delete-card", methods=["POST", "DELETE"])
@login_required
def delete_card():
    user = get_current_user()
    users.delete_card(user.id)
    if request.method == "DELETE":
        return answer_json(True, "Карта удалена.")
    flash("Карта удалена.", "success")
    return redirect(url_for("profile"))


@app.route("/my-tariff")
@login_required
def my_tariff():
    user = get_current_user()
    tariff = None
    payment_info = None
    if user.active_tariff:
        tariff = Tariff.get(user.active_tariff)
    for item in reversed(payments.get_all()):
        if str(item.get("user_id")) == str(user.id) and item.get("kind") == "tariff":
            if tariff and str(item.get("payload", {}).get("tariff_id")) != str(tariff.id):
                continue
            payment_info = item
            break
    pay_date = ""
    next_pay = ""
    if payment_info:
        pay_date = format_russian_date(payment_info.get("created_at"))
        next_pay = next_payment_date(payment_info.get("created_at"))
    return render_template("my_tariff.html", user=user, tariff=tariff, payment_info=payment_info, pay_date=pay_date, next_pay=next_pay)


@app.route("/buy-gb", methods=["POST"])
@login_required
def buy_gb():
    user = get_current_user()
    ok, message = users.buy_gb(user.id, request.form.get("gb", ""))
    if ok:
        flash(message, "success")
    else:
        flash(message, "error")
    return redirect(url_for("my_tariff"))


@app.route("/cancel-tariff", methods=["POST", "DELETE"])
@login_required
def cancel_tariff():
    user = get_current_user()
    if users.remove_tariff(user.id):
        if request.method == "DELETE":
            return answer_json(True, "Тариф отключён.")
        flash("Тариф отключён.", "success")
    else:
        if request.method == "DELETE":
            return answer_json(False, "У вас нет подключённого тарифа.", status=400)
        flash("У вас нет подключённого тарифа.", "warning")
    return redirect(url_for("my_tariff"))


@app.errorhandler(404)
def not_found(error):
    return render_template("404.html", simple_header=True, back_text="На главную", back_url=url_for("index")), 404


if __name__ == "__main__":
    app.run(debug=True, port=5001)
