import json
import os

DB_FILE = "database.json"

def load_db():
    if not os.path.exists(DB_FILE):
        return {"users": {}, "telegram_sessions": []}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return {"users": {}, "telegram_sessions": []}

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

class User:
    def __init__(self, **kwargs):
        self.user_id = str(kwargs.get("user_id"))
        self.is_vip = kwargs.get("is_vip", False)
        self.has_paid = kwargs.get("has_paid", False)
        self.star_count = kwargs.get("star_count", 100)
        self.groups = kwargs.get("groups", "")

class TelegramSession:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id")
        self.user_id = str(kwargs.get("user_id"))
        self.session_string = kwargs.get("session_string")
        self.account_name = kwargs.get("account_name", "حساب تليجرام")
        self.is_active = kwargs.get("is_active", True)

class JsonQuery:
    def __init__(self, data, model):
        self.data = data
        self.model = model
        self.filters = []

    def filter(self, *args, **kwargs):
        for key, value in kwargs.items():
            self.filters.append((key, value))
        return self

    def first(self):
        results = self.all()
        return results[0] if results else None

    def all(self):
        table = "users" if self.model == User else "telegram_sessions"
        items = self.data.get(table, [])
        if table == "users":
            items = [User(**v) for k, v in items.items()]
        else:
            items = [TelegramSession(**item) for item in items]
        
        filtered = []
        for item in items:
            match = True
            for key, val in self.filters:
                if str(getattr(item, key)) != str(val):
                    match = False
                    break
            if match:
                filtered.append(item)
        return filtered

    def update(self, values):
        table = "users" if self.model == User else "telegram_sessions"
        results = self.all()
        db_data = load_db()
        for item in results:
            if table == "users":
                if item.user_id in db_data["users"]:
                    db_data["users"][item.user_id].update(values)
            else:
                for s in db_data["telegram_sessions"]:
                    if s["id"] == item.id:
                        s.update(values)
        save_db(db_data)

class JsonSession:
    def __init__(self):
        self.data = load_db()

    def query(self, model):
        return JsonQuery(self.data, model)

    def add(self, obj):
        if isinstance(obj, User):
            self.data["users"][obj.user_id] = obj.__dict__
        elif isinstance(obj, TelegramSession):
            if not obj.id:
                obj.id = max([s["id"] for s in self.data["telegram_sessions"]] + [0]) + 1
            self.data["telegram_sessions"].append(obj.__dict__)

    def delete(self, obj):
        if isinstance(obj, User):
            self.data["users"].pop(obj.user_id, None)
        elif isinstance(obj, TelegramSession):
            self.data["telegram_sessions"] = [s for s in self.data["telegram_sessions"] if s["id"] != obj.id]

    def commit(self):
        save_db(self.data)

    def close(self):
        pass

def get_db():
    return JsonSession()
