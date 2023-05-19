"""Автоматичне укладання вправ із граматики української мови як іноземної"""

import stanza
import sqlite3
import tkinter as tk
import random
from collections import defaultdict
import re
import pymorphy3

con = sqlite3.connect('tasks.db')
cur = con.cursor()


class SQL:
    """Містить SQL-запити та методи створення БД вправ."""

    @staticmethod
    def choose_tasks(level: int, pos: str, set_number: int) -> dict[int, list]:
        """Створює список вправ, які підходять під вимоги користувача"""

        global con
        global cur

        # отримати список словоформ потрібного рівня
        cur.execute(f"""SELECT *
                        FROM {pos}_level
                        WHERE level_id = {level}""")
        level_list = [[description[0] for description in cur.description[1:]][i]
                      for i, boolean in enumerate(cur.fetchall()[0][1:]) if boolean == 1]

        # отримати список цільових слів за частиною мови та рівнем
        cur.execute(f"""SELECT text, sentence_id, token_index, pos_id, {", ".join(level_list)}
                        FROM token
                        INNER JOIN {pos}
                            ON token.pos_id = {pos}.{pos}_id
                        WHERE pos = '{pos}'
                            AND sentence_id IN
                                (SELECT sentence_id
                                FROM sentence_set
                                WHERE set_id = {set_number})
                            AND form IN {tuple(level_list)}""")
        corrects_list = [list(row) for row in cur.fetchall()]

        # отримати список стрижнів для цільових слів
        cur.execute(f"""SELECT text, sentence_id, token_index
                        FROM token
                        WHERE pos != '{pos}'
                            AND sentence_id IN
                                (SELECT sentence_id
                                FROM token
                                WHERE pos = '{pos}'
                                    AND sentence_id IN
                                        (SELECT sentence_id
                                        FROM sentence_set
                                        WHERE set_id = {set_number}))""")
        stems_list = [list(row) for row in cur.fetchall()]

        # почистити стрижні-дублікати
        stems = defaultdict(list)
        stems_numbers = set([correct[1] for correct in corrects_list])
        for i in stems_numbers:
            stems[i] = [j for j in corrects_list if j[1] == i]
            if len(stems[i]) > 1:
                stems[i] = random.sample(stems[i], 1)
            stems[i].append([j for j in stems_list if j[1] == i])

        return stems

    @staticmethod
    def add_tasks(task_set: list[str], sentences: dict[str, list[dict[str, str | int | dict[str, str | int] | None]]]) \
            -> None:
        """Додає новий користувацький набір вправ у БД"""

        global con
        global cur

        # вставити дані про новий набір вправ
        cur.execute(f"""INSERT INTO set (name, description)
                            VALUES {tuple(task_set)}""")
        cur.execute("""SELECT seq
                       FROM sqlite_sequence
                       WHERE name = 'set'""")
        set_id = cur.fetchall()[0][0]

        # вставити дані про речення набору
        for k, v in sentences.items():

            # перевірити, чи речення вже є у БД
            cur.execute(f"""SELECT sentence_id
                            FROM sentence
                            WHERE text = '{k}'""")
            try:
                sentence_id = cur.fetchall()[0][0]

            # речення нема у БД: додати його і дані про його токени
            except IndexError:
                cur.execute(f"""INSERT INTO sentence (text)
                                VALUES ('{k}')""")
                cur.execute("""SELECT seq
                                FROM sqlite_sequence
                                WHERE name = 'sentence'""")
                sentence_id = cur.fetchall()[0][0]

                SQL.add_tokens(v, sentence_id)

            # прив'язати речення до набору
            finally:
                cur.execute(f"""INSERT INTO sentence_set
                                VALUES ('{set_id}', '{sentence_id}')""")
                con.commit()

    @staticmethod
    def add_tokens(tokens: list[dict[str, str | int | dict[str, str | int] | None]], sentence_id: int) -> None:
        """Додає слова із речень у БД"""

        for token in tokens:

            # перевірити, чи цільова частина мови (має вказану форму)
            if token['form']:
                property_columns = list(token['properties'].keys())
                property_values = list(token['properties'].values())
                cur.execute(f"""SELECT {token['pos']}_id
                                FROM {token['pos']}
                                WHERE {token['form']} = '{token['text']}'
                                    AND {' AND '.join(f'{column} = ?' for column in property_columns)}""",
                            property_values)

                # перевірити наявність леми у таблиці
                try:
                    pos_id = cur.fetchall()[0][0]

                # леми нема у БД: додати її
                except IndexError:
                    pos_id = SQL.add_pos(token['pos'], token['forms'], property_columns, property_values)

            # нецільова частина мови: не прив'язувати до таблиці
            else:
                pos_id = None

            # вставити токени у таблицю
            query = """INSERT INTO token (text, sentence_id, token_index, pos, pos_id, form)
                            VALUES (?, ?, ?, ?, ?, ?)"""
            values = (token['text'], sentence_id, token['token_index'], token['pos'], pos_id, token['form'])
            cur.execute(query, values)

    @staticmethod
    def add_pos(pos: str, forms: dict[str, str], property_columns: list[str], property_values: list[str]) -> int:
        """Додає нову лему у БД"""

        # отримати список колонок і значень форм і граматичних категорій
        form_columns = list(forms.keys())
        form_values = list(forms.values())
        columns = tuple(form_columns + property_columns)
        values = tuple(form_values + property_values)

        # вставити дані про леми у таблицю
        cur.execute(f"""INSERT INTO {pos} {columns}
                        VALUES {values}""")
        cur.execute(f"""SELECT seq
                        FROM sqlite_sequence
                        WHERE name = '{pos}'""")
        pos_id = cur.fetchall()[0][0]

        return pos_id


class Token:
    """Обробляє слова із користувацького тексту"""

    def __init__(self, token_doc):
        self.token_doc = token_doc
        self.text = token_doc.text
        self.index = token_doc.id - 1
        self.pos = ''
        self.form = None
        self.forms = None
        self.properties = None

    def get_pos(self):
        pass

    def get_dict(self):
        return {'text': self.text, 'token_index': self.index, 'pos': self.pos, 'form': self.form, 'forms': self.forms,
                'properties': self.properties}


class Pronoun(Token):
    """Обробляє займенники із користувацького тексту"""


class Sentence:
    """Обробляє речення із користувацького тексту"""

    def __init__(self, sentence_doc: stanza.models.common.doc.Sentence):
        self.sentence_doc = sentence_doc
        self.text = sentence_doc.text
        self.tokens = None
        self.analyse_tokens()

    def analyse_tokens(self):
        for token in self.sentence_doc.tokens:
            self.tokens.append(Token(token).get_dict())

    def get_dict(self):
        return {self.text: self.tokens}


class Text:
    """Обробляє користувацький текст"""

    def __init__(self, file_path: str, task_set: list[str]):
        self.set = task_set
        self.text = None
        self.sentences = {}
        self.read_text(file_path)
        self.clean_text()
        nlp = stanza.Pipeline("uk")
        self.doc = nlp(self.text)
        global morph
        morph = pymorphy3.MorphAnalyzer(lang='uk')
        self.analyse_text()

    def read_text(self, file_path: str) -> None:
        """Зчитує текст із файлу"""
        with open(file_path, encoding="windows-1251") as file:
            self.text = file.read()

    def clean_text(self) -> None:
        """Уніфіковує апострофи та лапки у тексті"""

        single_quotes = ['`', '‘', '❮', '❯', '‚', '‛', '❛', '❜', '❟', 'ߵ', '´', 'ˊ', '｀', 'ʼ', 'ߴ', '՚', '＇', 'ʹ', 'ʻ',
                         'ʽ', 'ʾ', 'ˈ', '′', '‵', "'"]
        double_quotes = ['„', '⹂', '‟', '“', '”', '❝', '❞', '〝', '〞', '〟', '＂', 'ˮ', '‶', '"']

        for i in single_quotes:
            # знайти та замінити апострофи (між літерами)
            self.text = re.sub(f"(?<=[А-ЩЬЮЯҐЄІЇа-щьюяґєії]){i}(?=[А-ЩЬЮЯҐЄІЇа-щьюяґєії])", '’', self.text)

            # знайти та замінити ліві одинарні лапки
            self.text = re.sub(fr"(?<=\W){i}(?=\S)", '‹', self.text)

            # знайти та замінити праві одинарні лапки
            self.text = re.sub(fr"(?<=\S){i}(?=\W)", '›', self.text)

        for i in double_quotes:
            # знайти та замінити ліві подвійні лапки
            self.text = re.sub(fr"{i}(?=\S)", '«', self.text)

            # знайти та замінити праві подвійні лапки
            self.text = re.sub(fr"(?<=\S){i}", '»', self.text)

    def analyse_text(self) -> None:
        """Ініціює поділ на речення, подальший аналіз токенів і їхній запис у БД"""

        for sentence_doc in self.doc.sentences:
            self.sentences.update(Sentence(sentence_doc).get_dict())

        SQL.add_tasks(self.set, self.sentences)


class Body(tk.Frame):
    """"""


class Application(tk.Tk):
    """"""


if __name__ == '__main__':
    con = sqlite3.connect('tasks.db')
    cur = con.cursor()
    app = Application()
    app.mainloop()
    con.close()
