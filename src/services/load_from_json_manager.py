import json

from .load_from_xml_manager import get_skill_data

CLASSES_DATA_PATH = "data/classes.json"


def load_classes() -> dict[str, dict[str, any]]:
    with open(CLASSES_DATA_PATH, "r", encoding="utf-8") as file:
        classes = json.load(file)

    for _class in classes.values():
        _class.setdefault("constitution", 0)
        _class.setdefault("move", 0)

        stats = _class["stats_up"]
        stats.setdefault("hp", [])
        stats.setdefault("def", [])
        stats.setdefault("res", [])
        stats.setdefault("str", [])

        _class["skills"] = [
            get_skill_data(skill) for skill in _class.get("skills", ())
        ]

    return classes