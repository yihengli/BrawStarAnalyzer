"""
I develoepd this script then I realized there is actually an offical api to get battle log data. :(
"""

from typing import Dict, List

import requests
import simplejson

import bs4
import dropbox
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from loguru import logger


class BattleLogCrawler:
    def __init__(self, user_id: str, config: Dict, db_token: str = "") -> None:
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.90 Safari/537.36"
        }
        self.user_id = user_id
        self.hero_map = {i["avator"]: i["name"] for i in config["web"]["hero"]}
        self.target = config["web"]["target"]
        self.html = None
        self.cur_time = pd.NaT

        self._class_block = config["static"]["class_block"]
        self._class_res = config["static"]["class_result"]
        self._style_font_m = config["static"]["style_font_m"]
        self._style_font_s = config["static"]["style_font_s"]
        self._style_font_xs = config["static"]["style_font_xs"]
        self._img_mvp = config["static"]["img_mvp"]

        self.db_token = db_token

    def get_content(self) -> None:
        logger.debug("Sending Request...")
        response = requests.get(self.target.format(user_id=self.user_id), headers=self.headers)

        logger.debug("Response Rceived: {}".format(response.status_code))
        self.html = BeautifulSoup(response.content, "html.parser")
        self.cur_time = pd.Timestamp.now()

    def _parse_one_person(self, person: bs4.element.Tag, _stage: str, i: int) -> Dict:
        _trophy, _, _level, _name = [
            i.text.strip() for i in person.find_all("div", attrs={"style": self._style_font_xs})
        ]
        res = {
            "trophy": int(_trophy),
            "level": int(_level),
            "name": _name,
            "hero": self.hero_map[person.find("img").get("src")],
            "playerId": person.get("href").split("/")[-1],
            "isTeammate": False,
        }

        if _stage == "Duo Showdown":
            res["group"] = i // 2
            res["is_mvp"] = np.nan
        elif _stage == "Showdown":
            res["group"] = i
            res["is_mvp"] = np.nan
        else:
            res["group"] = np.nan
            res["is_mvp"] = person.find("img", attrs={"src": self._img_mvp}) is not None
        return res

    def _assign_teammates(self, _people: List[Dict], _stage: str) -> List[Dict]:
        i_me = 0
        for i in _people:
            if i["playerId"] == self.user_id:
                break
            i_me += 1

        if _stage == "Duo Showdown":
            _people[i_me]["is_Teammate"] = True
            if i_me % 2 == 0:
                _people[i_me + 1]["isTeammate"] = True
            else:
                _people[i_me - 1]["isTeammate"] = True
        elif _stage == "Showdown":
            _people[i_me]["isTeammate"] = True
        else:
            if i_me // 3 == 0:
                for i in range(3):
                    _people[i]["isTeammate"] = True
            else:
                for i in range(5, 2, -1):
                    _people[i]["isTeammate"] = True
        return _people

    def _parse_one_block(self, block: bs4.element.Tag) -> Dict:
        _result = block.find("div", class_=self._class_res).text.strip()
        _stage, _rewards = [i.text.strip() for i in block.find_all("div", attrs={"style": self._style_font_m})]
        _type, _time, _map = [i.text.strip() for i in block.find_all("div", attrs={"style": self._style_font_s})]
        people = block.find_all("a")
        _people = [self._parse_one_person(person, _stage, i) for i, person in enumerate(people)]
        _people = self._assign_teammates(_people, _stage)
        return {
            "match": _result,
            "stage": _stage,
            "map": _map,
            "rewards": int(_rewards),
            "type": _type,
            "time": _time,
            "players": _people,
        }

    def parse(self) -> List[Dict]:
        return [self._parse_one_block(block) for block in self.html.find_all("div", class_=self._class_block)]

    def run(self):
        self.get_content()
        res = self.parse()

        if self.db_token:
            dbx = dropbox.Dropbox(self.db_token)
            _ = dbx.files_upload(
                bytes(simplejson.dumps(res, indent=4, ignore_nan=True), encoding="utf-8"),
                "/{user}/{d:%Y%m%d}/{d:%Y%m%d_%H%M%S}.json".format(user=self.user_id, d=pd.Timestamp.now()),
            )
