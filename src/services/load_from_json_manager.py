import json
from src.services.language import *

from lxml import etree

from src.game_entities.skill import Skill


CLASSES_DATA_PATH = "data/classes.json"
skills_data = {}

def get_skill_data(name) -> Skill:
    """

    :param name:
    :return:
    """
    if name not in skills_data:
        # Required data
        skill_element = etree.parse("data/skills.xml").find(name)
        formatted_name = skill_element.find("name/" + language)
        if formatted_name is not None:
            formatted_name = formatted_name.text.strip()
        else:
            formatted_name = skill_element.find("name/en").text.strip()
        nature = skill_element.find("type").text.strip()
        description = get_localized_string(skill_element.find("info")).strip()

        # Not required elements
        power = 0
        power_element = skill_element.find("power")
        if power_element is not None:
            power = int(power_element.text.strip())
        stats = []
        stats_element = skill_element.find("stats")
        if stats_element is not None:
            stats = list(stats_element.text.replace(" ", "").split(","))
        alterations = []
        alterations_element = skill_element.find("alteration")
        if alterations_element is not None:
            alterations = list(alterations_element.text.replace(" ", "").split(","))

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