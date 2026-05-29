import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


class FileStorage:
    def __init__(self, filename):
        self.filename = filename
        self.path = DATA_DIR / filename

    def read(self, default=None):
        if default is None:
            default = []
        if not self.path.exists():
            self.write(default)
            return default
        try:
            with self.path.open("r", encoding="utf-8") as file:
                return json.load(file)
        except json.JSONDecodeError:
            return default

    def write(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

    def next_id(self, items):
        if not items:
            return 1
        biggest = 0
        for item in items:
            try:
                current = int(item.get("id", 0))
            except ValueError:
                current = 0
            if current > biggest:
                biggest = current
        return biggest + 1

    def add_record(self, record):
        items = self.read([])
        if "id" not in record or record.get("id") in (None, ""):
            record["id"] = self.next_id(items)
        items.append(record)
        self.write(items)
        return record

    def find_record(self, field, value):
        items = self.read([])
        for item in items:
            if str(item.get(field, "")) == str(value):
                return item
        return None

    def update_record(self, record_id, changes):
        items = self.read([])
        for i in range(len(items)):
            if str(items[i].get("id")) == str(record_id):
                for key in changes:
                    if key != "id":
                        items[i][key] = changes[key]
                self.write(items)
                return items[i]
        return None

    def delete_record(self, record_id):
        items = self.read([])
        new_items = []
        deleted = False
        for item in items:
            if str(item.get("id")) == str(record_id):
                deleted = True
            else:
                new_items.append(item)
        if deleted:
            self.write(new_items)
        return deleted


# Эти функции оставлены отдельно, как в файловой части лабораторной.
def read_json(filename, default=None):
    return FileStorage(filename).read(default)


def write_json(filename, data):
    FileStorage(filename).write(data)


def add_record(filename, record):
    return FileStorage(filename).add_record(record)


def find_record(filename, field, value):
    return FileStorage(filename).find_record(field, value)


def update_record(filename, record_id, changes):
    return FileStorage(filename).update_record(record_id, changes)


def delete_record(filename, record_id):
    return FileStorage(filename).delete_record(record_id)
