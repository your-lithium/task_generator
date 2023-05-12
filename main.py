"""Автоматичне укладання вправ із граматики української мови як іноземної"""


import stanza
import sqlite3
import tkinter as tk
import random


class SQL:
    """Містить SQL-запити та методи створення БД вправ."""

    def __init__(self) -> None:
        con = sqlite3.connect('tasks.db')
        self.cur = con.cursor()

    def tasks_choice(self, level: str, pos: str, set_number: int) -> list[int]:
        """Створює список вправ, які підходять під вимоги користувача"""

        self.cur.execute(f"""SELECT *
                             FROM {pos}_levels
                             WHERE level_id = {level}""")
        level_list = [[description[0] for description in self.cur.description[1:]][i]
                      for i, bool in enumerate(self.cur.fetchall()[0][1:]) if bool == 1]

        self.cur.execute(f"""SELECT text, sentence_id, token_index, pos_id, {", ".join(level_list)}
                             FROM tokens
                             INNER JOIN {pos}s
                                ON tokens.pos_id = {pos}s.{pos}_id
                             WHERE pos = '{pos}'
                                AND sentence_id IN
                                    (SELECT sentence_id
                                     FROM sentences_sets
                                     WHERE set_id = {set_number})
                                AND form IN {tuple(level_list)}""")
        corrects_list = [list(row) for row in self.cur.fetchall()]
        print(corrects_list)

        self.cur.execute(f"""SELECT text, sentence_id, token_index
                             FROM tokens
                             WHERE pos != '{pos}'
                                   AND sentence_id IN
                                       (SELECT sentence_id
                                        FROM tokens
                                        WHERE pos = '{pos}'
                                            AND sentence_id IN
                                                (SELECT sentence_id
                                                 FROM sentences_sets
                                                 WHERE set_id = {set_number}))""")
        stems_list = [list(row) for row in self.cur.fetchall()]
        print(stems_list)

        # duplicates = []
        # duplicate_check = set([correct[1] for correct in corrects_list])
        # if len(duplicate_check) < len(corrects_list):



class Word:
    """"""


class Pronoun(Word):
    """"""


class Sentence:
    """"""


class Text:
    """"""


class Executor:
    """"""


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
