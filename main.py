"""Автоматичне укладання вправ із граматики української мови як іноземної"""

import stanza
import sqlite3
import tkinter as tk
import random
from collections import defaultdict

con = sqlite3.connect('tasks.db')
cur = con.cursor()


class SQL:
    """Містить SQL-запити та методи створення БД вправ."""

    @staticmethod
    def choose_tasks(level: int, pos: str, set_number: int) -> dict[int, list]:
        """Створює список вправ, які підходять під вимоги користувача"""

        global con
        global cur

        cur.execute(f"""SELECT *
                        FROM {pos}_level
                        WHERE level_id = {level}""")
        level_list = [[description[0] for description in cur.description[1:]][i]
                      for i, boolean in enumerate(cur.fetchall()[0][1:]) if boolean == 1]
        # print(level_list)

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
        # print(corrects_list)

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
        # print(stems_list)

        stems = defaultdict(list)
        stems_numbers = set([correct[1] for correct in corrects_list])
        for i in stems_numbers:
            stems[i] = [j for j in corrects_list if j[1] == i]
            if len(stems[i]) > 1:
                stems[i] = random.sample(stems[i], 1)
            stems[i].append([j for j in stems_list if j[1] == i])
        # print(stems)

        return stems

    @staticmethod
    def add_tasks(sample: list[str], sentences: dict[str, list[dict[str, str | int | dict[str, str | int] | None]]]) \
            -> None:
        """Додає новий користувацький набір вправ у БД"""

        global con
        global cur

        cur.execute(f"""INSERT INTO set (name, description)
                            VALUES {tuple(sample)}""")

        cur.execute("""SELECT seq
                       FROM sqlite_sequence
                       WHERE name = 'set'""")
        sample_id = cur.fetchall()[0][0]
        # print(sample_id)

        for k, v in sentences.items():
            cur.execute(f"""SELECT sentence_id
                            FROM sentence
                            WHERE text = '{k}'""")
            try:
                sentence_id = cur.fetchall()[0][0]
            except IndexError:
                cur.execute(f"""INSERT INTO sentence (text)
                                VALUES ('{k}')""")
                cur.execute("""SELECT seq
                                FROM sqlite_sequence
                                WHERE name = 'sentence'""")
                sentence_id = cur.fetchall()[0][0]

                SQL.add_tokens(v, sentence_id)
            finally:
                cur.execute(f"""INSERT INTO sentence_set
                                VALUES ('{sample_id}', '{sentence_id}')""")
                con.commit()

    @staticmethod
    def add_tokens(tokens: list[dict[str, str | int | dict[str, str | int] | None]], sentence_id: int) -> None:
        """Додає слова із речень у БД"""

        for token in tokens:
            print()
            if token['form']:  # перевірка цільової частини мови
                property_columns = list(token['properties'].keys())
                property_values = list(token['properties'].values())
                cur.execute(f"""SELECT {token['pos']}_id
                                FROM {token['pos']}
                                WHERE {token['form']} = '{token['text']}'
                                    AND {' AND '.join(f'{column} = ?' for column in property_columns)}""",
                            property_values)

                try:  # перевірка наявності леми у таблиці
                    pos_id = cur.fetchall()[0][0]
                except IndexError:
                    pos_id = SQL.add_pos(token['pos'], token['forms'], property_columns, property_values)

            else:
                pos_id = None

            query = """INSERT INTO token (text, sentence_id, token_index, pos, pos_id, form)
                            VALUES (?, ?, ?, ?, ?, ?)"""
            values = (token['text'], sentence_id, token['token_index'], token['pos'], pos_id, token['form'])
            cur.execute(query, values)

    @staticmethod
    def add_pos(pos: str, forms: dict[str, str], property_columns: list[str], property_values: list[str]) -> int:
        """Додає нову лему у БД"""

        form_columns = list(forms.keys())
        form_values = list(forms.values())

        columns = tuple(form_columns + property_columns)
        values = tuple(form_values + property_values)

        cur.execute(f"""INSERT INTO {pos} {columns}
                        VALUES {values}""")

        cur.execute(f"""SELECT seq
                        FROM sqlite_sequence
                        WHERE name = '{pos}'""")
        pos_id = cur.fetchall()[0][0]

        return pos_id


class Word:
    """"""


class Pronoun(Word):
    """"""


class Sentence:
    """"""


class Text:
    """"""

    def __init__(self, file_name: str):
        pass


class Body(tk.Frame):
    """"""


class Application(tk.Tk):
    """"""


if __name__ == '__main__':
    con = sqlite3.connect('tasks.db')
    cur = con.cursor()
    # nlp = stanza.Pipeline("uk")
    app = Application()
    app.mainloop()
    con.close()
