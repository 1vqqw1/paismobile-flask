import re
from datetime import date, datetime, timedelta

from services.security import Password
from services.storage import FileStorage

RUS = re.compile(r'^[а-яёА-ЯЁ]+$')
SPECIALS = set('!@#$%^&*()_+-=[]{}|;:\'",.<>?/`~№')

CITY_UTC = {
    "Москва": 3, "Санкт-Петербург": 3, "Казань": 3, "Краснодар": 3,
    "Нижний Новгород": 3, "Ростов-на-Дону": 3, "Сочи": 3,
    "Волгоград": 3, "Воронеж": 3, "Мурманск": 3, "Архангельск": 3,
    "Ярославль": 3, "Калининград": 2, "Самара": 4, "Уфа": 5,
    "Екатеринбург": 5, "Омск": 6, "Новосибирск": 7, "Красноярск": 7,
    "Владивосток": 10,
}


def utc_now():
    return datetime.utcnow()


def city_now(city_name):
    offset = CITY_UTC.get(city_name, 3)
    return utc_now() + timedelta(hours=offset)


def city_str(city_name):
    return city_now(city_name).strftime("%d.%m.%Y %H:%M:%S")


def city_tz(city_name):
    return "UTC+" + str(CITY_UTC.get(city_name, 3))


def normalize_phone(phone):
    digits = ""
    for ch in str(phone):
        if ch.isdigit():
            digits += ch
    if len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    if len(digits) == 11 and digits[0] == "7":
        return "+" + digits
    return str(phone).strip()


def phone_digits(phone):
    result = ""
    for ch in str(phone):
        if ch.isdigit():
            result += ch
    if len(result) == 11 and result[0] == "8":
        result = "7" + result[1:]
    return result


def check_rus_name(value, label):
    value = str(value).strip()
    if not value:
        return "", label + " не может быть пустым."
    if not RUS.match(value):
        return "", label + " — только русские буквы."
    return value[0].upper() + value[1:], ""


def check_password_rules(password):
    errors = []
    if len(password) < 8:
        errors.append("минимум 8 символов")
    if len(password) > 20:
        errors.append("максимум 20 символов")
    if not any(ch.islower() and ch.isascii() for ch in password):
        errors.append("нет строчной латинской буквы")
    if not any(ch.isupper() and ch.isascii() for ch in password):
        errors.append("нет заглавной латинской буквы")
    if not any(ch in SPECIALS for ch in password):
        errors.append("нет спецсимвола")
    if errors:
        return "Пароль: " + "; ".join(errors) + "."
    return ""


def check_card(form):
    card = form.get("card", "").replace(" ", "").replace("-", "").strip()
    holder = form.get("holder", "").strip()
    expire = form.get("expire", "").replace(" ", "").strip()
    cvv = form.get("cvv", "").strip()

    if not re.fullmatch(r'\d{16}', card):
        return None, "Номер карты должен содержать ровно 16 цифр."
    if not holder:
        return None, "Введите имя владельца карты."
    if not re.fullmatch(r'(0[1-9]|1[0-2])/\d{2}', expire):
        return None, "Срок действия карты должен быть в формате ММ/ГГ."
    month = int(expire[:2])
    year = 2000 + int(expire[3:])
    now = utc_now()
    if year < now.year or (year == now.year and month < now.month):
        return None, "Карта просрочена."
    if not re.fullmatch(r'\d{3}', cvv):
        return None, "CVV должен содержать ровно 3 цифры."

    return {
        "number": card,
        "holder": holder,
        "expiry": expire,
        "cvv": cvv,
        "last4": card[-4:],
    }, ""


class Tariff:
    storage = FileStorage("tariffs.json")
    catalog = []

    def __init__(self, tid, name, price, calls, internet, sms, features, subtitle="", period="₽/мес", badge="", short=None, active=False):
        self.id = tid
        self.name = name
        self.price = price
        self.calls = calls
        self.internet = internet
        self.sms = sms
        self.features = features
        self.subtitle = subtitle
        self.period = period
        self.badge = badge
        self.short = short or []
        self.active = active

    def __str__(self):
        return self.name + " — " + str(self.price) + " ₽/мес"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "subtitle": self.subtitle,
            "price": self.price,
            "period": self.period,
            "badge": self.badge,
            "calls": self.calls,
            "internet": self.internet,
            "sms": self.sms,
            "features": self.features,
            "short": self.short,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, item):
        return cls(
            item.get("id", ""),
            item.get("name", ""),
            int(item.get("price", 0)),
            item.get("calls", ""),
            item.get("internet", ""),
            item.get("sms", ""),
            item.get("features", []),
            item.get("subtitle", ""),
            item.get("period", "₽/мес"),
            item.get("badge", ""),
            item.get("short", []),
            item.get("active", False),
        )

    @classmethod
    def load_catalog(cls):
        cls.catalog = []
        for item in cls.storage.read([]):
            cls.catalog.append(cls.from_dict(item))

    @classmethod
    def get_all(cls):
        cls.load_catalog()
        return cls.catalog

    @classmethod
    def get(cls, tid):
        cls.load_catalog()
        for tariff in cls.catalog:
            if str(tariff.id) == str(tid):
                return tariff
        return None

    @classmethod
    def get_featured(cls):
        needed = ["serafim", "arkhangel", "prestol"]
        result = []
        for tariff in cls.get_all():
            if tariff.id in needed:
                result.append(tariff)
        return result


class City:
    def __init__(self, name, area, network, tariffs):
        self.name = name
        self.area = area
        self.network = network
        self.tariffs = tariffs

    def __str__(self):
        return self.name + " — " + self.network


class CityRegion:
    def __init__(self, region, city_list):
        self.region = region
        self.city_list = city_list


class CityBook:
    def __init__(self):
        self.storage = FileStorage("cities.json")
        self.regions = []

    def load(self, search_text=""):
        self.regions = []
        search_text = search_text.strip().lower()
        for region in self.storage.read([]):
            city_list = []
            for item in region.get("items", []):
                city = City(
                    item.get("name", ""),
                    item.get("area", ""),
                    item.get("network", ""),
                    item.get("tariffs", 0),
                )
                text = (city.name + " " + city.area).lower()
                if not search_text or search_text in text:
                    city_list.append(city)
            if city_list:
                self.regions.append(CityRegion(region.get("region", ""), city_list))
        return self.regions

    def names(self):
        result = []
        for region in self.storage.read([]):
            for item in region.get("items", []):
                result.append(item.get("name", ""))
        result = [name for name in result if name]
        result.sort()
        return result

    def get(self, name):
        for region in self.storage.read([]):
            for item in region.get("items", []):
                if item.get("name", "").lower() == str(name).lower():
                    return City(
                        item.get("name", ""),
                        item.get("area", ""),
                        item.get("network", ""),
                        item.get("tariffs", 0),
                    )
        return None


class Promo:
    storage = FileStorage("promos.json")
    catalog = []

    def __init__(self, pid, title, tag, text, promo_type="simple", discount=0, months=0, bonus_gb=0, countries=0, req_tariff=""):
        self.id = pid
        self.title = title
        self.tag = tag
        self.text = text
        self.type = promo_type
        self.discount = discount
        self.months = months
        self.bonus_gb = bonus_gb
        self.countries = countries
        self.req_tariff = req_tariff

    def __str__(self):
        return self.title

    @classmethod
    def from_dict(cls, item, number=0):
        return cls(
            item.get("id", number),
            item.get("title", ""),
            item.get("tag", ""),
            item.get("text", ""),
            item.get("type", "simple"),
            int(item.get("discount", 0)),
            int(item.get("months", 0)),
            int(item.get("bonus_gb", 0)),
            int(item.get("countries", 0)),
            item.get("req_tariff", ""),
        )

    @classmethod
    def load_catalog(cls):
        cls.catalog = []
        number = 1
        for item in cls.storage.read([]):
            cls.catalog.append(cls.from_dict(item, number))
            number += 1

    @classmethod
    def get_all(cls):
        cls.load_catalog()
        return cls.catalog

    @classmethod
    def get(cls, promo_id):
        for promo in cls.get_all():
            if str(promo.id) == str(promo_id):
                return promo
        return None

    def check_eligibility(self, user):
        if str(self.id) in [str(pid) for pid in user.promotions]:
            return False, "Эта акция уже активирована."
        if self.type in ("birthday", "roaming") and not user.active_tariff:
            return False, "Сначала подключите тариф."
        if self.type == "bundle" and user.active_tariff != self.req_tariff:
            tariff = Tariff.get(self.req_tariff)
            name = tariff.name if tariff else self.req_tariff
            return False, "Акция доступна только для тарифа «" + name + "»."
        if self.type == "birthday":
            if not user.birth_date:
                return False, "Укажите дату рождения в настройках профиля."
            try:
                birth = datetime.strptime(user.birth_date, "%Y-%m-%d")
            except ValueError:
                return False, "Дата рождения указана неверно."
            today = city_now(user.city)
            age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
            if age < 18:
                return False, "Акция доступна с 18 лет."
            if birth.day != today.day or birth.month != today.month:
                return False, "Акцию можно активировать только в день рождения."
        return True, ""

    def apply(self, user, form=None):
        form = form or {}
        ok, reason = self.check_eligibility(user)
        if not ok:
            return False, reason

        if self.type == "transfer":
            user.promotions.append(str(self.id))
            return True, "Акция активирована. Скидка будет учтена при следующей оплате."

        if self.type == "bonus_gb":
            user.extra_gb = int(user.extra_gb) + int(self.bonus_gb or 10)
            user.promotions.append(str(self.id))
            return True, "+" + str(self.bonus_gb or 10) + " ГБ добавлено к вашему тарифу."

        if self.type == "birthday":
            user.promotions.append(str(self.id))
            return True, "Скидка ко дню рождения активирована."

        if self.type == "cashback":
            friend_phone = normalize_phone(form.get("friend_phone", ""))
            user.pending_cashback.append({
                "friend_phone": friend_phone,
                "created_at": utc_now().isoformat(),
                "completed": False,
            })
            user.promotions.append(str(self.id))
            return True, "Кешбэк за друга активирован."

        if self.type == "roaming":
            user.promotions.append(str(self.id))
            return True, "Роуминг без границ активирован."

        if self.type == "bundle":
            user.promotions.append(str(self.id))
            return True, "Домашний интернет в подарок активирован."

        user.promotions.append(str(self.id))
        return True, "Акция активирована."

    @classmethod
    def check_cashback(cls, new_phone, book):
        now = utc_now()
        new_digits = phone_digits(new_phone)
        changed = False
        for user in book.get_all():
            for bonus in user.pending_cashback:
                if bonus.get("completed"):
                    continue
                friend_digits = phone_digits(bonus.get("friend_phone", ""))
                if friend_digits and friend_digits != new_digits:
                    continue
                created = bonus.get("created_at", "")
                try:
                    created_date = datetime.fromisoformat(created)
                except ValueError:
                    created_date = now
                if (now - created_date).total_seconds() <= 900:
                    bonus["completed"] = True
                    user.balance = int(user.balance) + 50
                    book.save_user(user)
                    changed = True
        return changed


class Subscriber:
    def __init__(self, uid, first_name, last_name, phone, email, password_hash, city):
        self.id = uid
        self.first_name = first_name
        self.last_name = last_name
        self.phone = phone
        self.email = email
        self.password_hash = password_hash
        self.city = city
        self.birth_date = ""
        self.gender = ""
        self.balance = 0
        self.active_tariff = None
        self.created_at = date.today().isoformat()
        self.tariff_history = []
        self.extra_gb = 0
        self.promotions = []
        self.card = None
        self.pending_cashback = []
        self.sub_type = "Обычный"

    def __str__(self):
        return self.first_name + " " + self.last_name + " (" + self.phone + ")"

    def to_dict(self):
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "phone": self.phone,
            "email": self.email,
            "password_hash": self.password_hash,
            "city": self.city,
            "birth_date": self.birth_date,
            "gender": self.gender,
            "balance": self.balance,
            "active_tariff": self.active_tariff,
            "created_at": self.created_at,
            "tariff_history": self.tariff_history,
            "extra_gb": self.extra_gb,
            "promotions": self.promotions,
            "card": self.card,
            "pending_cashback": self.pending_cashback,
            "sub_type": self.sub_type,
        }

    @classmethod
    def from_dict(cls, item):
        user = cls(
            item.get("id"),
            item.get("first_name", ""),
            item.get("last_name", ""),
            item.get("phone", ""),
            item.get("email", ""),
            item.get("password_hash", ""),
            item.get("city", ""),
        )
        user.birth_date = item.get("birth_date", "")
        user.gender = item.get("gender", "")
        user.balance = item.get("balance", 0)
        user.active_tariff = item.get("active_tariff")
        if user.active_tariff == "":
            user.active_tariff = None
        user.created_at = item.get("created_at", date.today().isoformat())
        user.tariff_history = item.get("tariff_history", [])
        user.extra_gb = item.get("extra_gb", 0)
        user.promotions = item.get("promotions", [])
        user.card = item.get("card")
        user.pending_cashback = item.get("pending_cashback", [])
        user.sub_type = item.get("sub_type", "Обычный")
        return user

    def check_password(self, password):
        return Password.check(password, self.password_hash)

    def set_tariff(self, tariff_id):
        tariff = Tariff.get(tariff_id)
        if not tariff:
            return False
        action = "Подключён" if not self.active_tariff else "Сменён на"
        self.active_tariff = tariff.id
        self.tariff_history.append({
            "date": city_str(self.city),
            "tz": city_tz(self.city),
            "action": action,
            "tariff_name": tariff.name,
            "tariff_id": tariff.id,
            "price": tariff.price,
        })
        return True

    def remove_tariff(self):
        if not self.active_tariff:
            return False
        tariff = Tariff.get(self.active_tariff)
        name = tariff.name if tariff else self.active_tariff
        price = tariff.price if tariff else 0
        self.tariff_history.append({
            "date": city_str(self.city),
            "tz": city_tz(self.city),
            "action": "Отключён",
            "tariff_name": name,
            "tariff_id": self.active_tariff,
            "price": price,
        })
        self.active_tariff = None
        return True

    def add_balance(self, amount):
        self.balance = int(self.balance) + int(amount)
        return self.balance

    def buy_gb(self, gb):
        try:
            gb = int(gb)
        except ValueError:
            return False, "Введите целое количество ГБ."
        if gb <= 0:
            return False, "Количество ГБ должно быть больше нуля."
        cost = gb * 50
        if int(self.balance) < cost:
            return False, "Недостаточно средств. Нужно " + str(cost) + " ₽."
        self.balance = int(self.balance) - cost
        self.extra_gb = int(self.extra_gb) + gb
        return True, "+" + str(gb) + " ГБ подключено за " + str(cost) + " ₽."

    def save_card(self, card):
        self.card = card

    def delete_card(self):
        self.card = None

    def update_profile(self, form, city_names):
        first_name, error = check_rus_name(form.get("first_name", ""), "Имя")
        if error:
            return error
        last_name, error = check_rus_name(form.get("last_name", ""), "Фамилия")
        if error:
            return error
        phone = normalize_phone(form.get("phone", ""))
        if not re.fullmatch(r'\+7\d{10}', phone):
            return "Телефон должен быть в формате +7XXXXXXXXXX."
        email = form.get("email", "").strip().lower()
        if not email or "@" not in email:
            return "Введите корректный email."
        city = form.get("city", "").strip()
        if city and city not in city_names:
            return "Выберите город из списка."

        self.first_name = first_name
        self.last_name = last_name
        self.birth_date = form.get("birth_date", "").strip()
        self.gender = form.get("gender", "").strip()
        self.phone = phone
        self.email = email
        self.city = city
        return ""

    def change_password(self, old_password, new_password, confirm):
        if old_password and not self.check_password(old_password):
            return False, "Текущий пароль введён неверно."
        if not new_password:
            return True, "Пароль не изменялся."
        error = check_password_rules(new_password)
        if error:
            return False, error
        if new_password != confirm:
            return False, "Новый пароль и подтверждение не совпадают."
        self.password_hash = Password.make(new_password)
        return True, "Пароль обновлён."


class SubscriberBook:
    def __init__(self):
        self.storage = FileStorage("users.json")
        self.cities = CityBook()

    def get_all(self):
        users = []
        for item in self.storage.read([]):
            users.append(Subscriber.from_dict(item))
        return users

    def get(self, user_id):
        if not user_id:
            return None
        for user in self.get_all():
            if str(user.id) == str(user_id):
                return user
        return None

    def save_user(self, user):
        return self.storage.update_record(user.id, user.to_dict())

    def find_by_login(self, login):
        login = str(login).strip().lower()
        digits = phone_digits(login)
        for user in self.get_all():
            if user.email.lower() == login:
                return user
            if phone_digits(user.phone) == digits and digits:
                return user
        return None

    def login(self, login, password):
        user = self.find_by_login(login)
        if user and user.check_password(password):
            return user
        return None

    def add(self, form):
        first_name, error = check_rus_name(form.get("first_name", ""), "Имя")
        if error:
            return None, error
        last_name, error = check_rus_name(form.get("last_name", ""), "Фамилия")
        if error:
            return None, error

        phone = normalize_phone(form.get("phone", ""))
        email = form.get("email", "").strip().lower()
        city = form.get("city", "").strip()
        password = form.get("password", "")
        confirm = form.get("password_confirm", "")

        if not re.fullmatch(r'\+7\d{10}', phone):
            return None, "Телефон должен быть в формате +7XXXXXXXXXX."
        if not email or "@" not in email:
            return None, "Введите корректный email."
        if city not in self.cities.names():
            return None, "Выберите город из списка."
        if self.find_by_login(email):
            return None, "Пользователь с таким email уже существует."
        if self.find_by_login(phone):
            return None, "Пользователь с таким телефоном уже существует."
        error = check_password_rules(password)
        if error:
            return None, error
        if password != confirm:
            return None, "Пароли не совпадают."

        user = Subscriber(None, first_name, last_name, phone, email, Password.make(password), city)
        record = self.storage.add_record(user.to_dict())
        user = Subscriber.from_dict(record)
        Promo.check_cashback(user.phone, self)
        return user, None

    def update_profile(self, user_id, form):
        user = self.get(user_id)
        if not user:
            return None, "Пользователь не найден."
        old_email = user.email.lower()
        old_phone = phone_digits(user.phone)
        error = user.update_profile(form, self.cities.names())
        if error:
            return None, error

        for other in self.get_all():
            if str(other.id) == str(user.id):
                continue
            if other.email.lower() == user.email.lower() and user.email.lower() != old_email:
                return None, "Такой email уже занят."
            if phone_digits(other.phone) == phone_digits(user.phone) and phone_digits(user.phone) != old_phone:
                return None, "Такой телефон уже занят."

        self.save_user(user)
        return user, ""

    def change_password(self, user_id, old_password, new_password, confirm):
        user = self.get(user_id)
        if not user:
            return False, "Пользователь не найден."
        ok, message = user.change_password(old_password, new_password, confirm)
        if ok:
            self.save_user(user)
        return ok, message

    def set_tariff(self, user_id, tariff_id):
        user = self.get(user_id)
        if not user:
            return None
        if user.set_tariff(tariff_id):
            Promo.check_cashback(user.phone, self)
            self.save_user(user)
            return user
        return None

    def remove_tariff(self, user_id):
        user = self.get(user_id)
        if not user:
            return False
        result = user.remove_tariff()
        self.save_user(user)
        return result

    def add_balance(self, user_id, amount):
        user = self.get(user_id)
        if not user:
            return 0
        balance = user.add_balance(amount)
        self.save_user(user)
        return balance

    def buy_gb(self, user_id, gb):
        user = self.get(user_id)
        if not user:
            return False, "Пользователь не найден."
        ok, message = user.buy_gb(gb)
        self.save_user(user)
        return ok, message

    def save_card(self, user_id, card):
        user = self.get(user_id)
        if not user:
            return None
        user.save_card(card)
        self.save_user(user)
        return user

    def delete_card(self, user_id):
        user = self.get(user_id)
        if not user:
            return None
        user.delete_card()
        self.save_user(user)
        return user

    def activate_promo(self, user_id, promo_id, form=None):
        user = self.get(user_id)
        promo = Promo.get(promo_id)
        if not user:
            return False, "Пользователь не найден."
        if not promo:
            return False, "Акция не найдена."
        ok, message = promo.apply(user, form)
        if ok:
            self.save_user(user)
        return ok, message


class Payment:
    def __init__(self, kind, amount, user_id, payload):
        self.kind = kind
        self.amount = int(amount)
        self.user_id = user_id
        self.payload = payload
        self.status = "paid"
        self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self):
        return {
            "kind": self.kind,
            "amount": self.amount,
            "user_id": self.user_id,
            "payload": self.payload,
            "status": self.status,
            "created_at": self.created_at,
        }


class PaymentBook:
    def __init__(self):
        self.storage = FileStorage("payments.json")

    def get_all(self):
        return self.storage.read([])

    def add(self, kind, amount, user_id, payload):
        payment = Payment(kind, amount, user_id, payload)
        return self.storage.add_record(payment.to_dict())
