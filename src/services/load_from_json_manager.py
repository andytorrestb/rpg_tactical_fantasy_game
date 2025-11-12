import json
from src.services.language import *

from lxml import etree

from src.game_entities.skill import Skill


CLASSES_DATA_PATH = "data/classes.json"
SKILLS_DATA_PATH = "data/skills.json"
skills_data = {}

def get_skill_data(name) -> Skill:
    """

    :param name:
    :return:
    """
    if name not in skills_data:
        # Required data
        with open(SKILLS_DATA_PATH, "r", encoding="utf-8") as file:
            skills_json = json.load(file)
            skill_element = skills_json[name]

            # Get localized name (fall back to english)
            formatted_name = skill_element["name"].get(language, skill_element["name"]["en"])
            nature = skill_element["type"]
            
            # Get localized description (fall back to english)
            description = skill_element["info"].get(language, skill_element["info"]["en"])

            # Not required elements
            power = skill_element.get("power", 0)
            stats = skill_element.get("stats", [])
            
            # Handle alteration/alterations field
            alterations = []
            if "alteration" in skill_element:
                if isinstance(skill_element["alteration"], list):
                    alterations = skill_element["alteration"]
                else:
                    alterations = [skill_element["alteration"]]
            elif "alterations" in skill_element:
                if isinstance(skill_element["alterations"], list):
                    alterations = skill_element["alterations"]
                else:
                    alterations = [skill_element["alterations"]]

            skills_data[name] = Skill(
                name, formatted_name, nature, description, power, stats, alterations
            )
    return skills_data[name]


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