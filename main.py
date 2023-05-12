"""Автоматичне укладання вправ із граматики української мови як іноземної"""


import stanza
import sqlite3
import tkinter as tk


class SQL:
    """Містить SQL-запити та методи створення БД вправ."""

    def __init__(self) -> None:
        con = sqlite3.connect('tasks.db')
        self.cur = con.cursor()

    def tasks_choice(self, pos: str, set_number: int) -> list[int]:  # + level
        """Створює список вправ, які підходять під вимоги користувача"""

        self.cur.execute(f"""SELECT sentence_id
                             FROM sentences_sets
                             WHERE set_id = {set_number}""")
        set_sents_list = tuple(list(row)[0] for row in self.cur.fetchall())
        print(set_sents_list)

        self.cur.execute(f"""SELECT sentence_id
                             FROM tokens
                             WHERE pos = '{pos}'
                                AND sentence_id IN {set_sents_list}""")
        pos_sents_list = tuple(list(row)[0] for row in self.cur.fetchall())
        print(pos_sents_list)

        self.cur.execute(f"""SELECT text, sentence_id, token_index, pos, pos_id
                             FROM tokens
                             WHERE sentence_id IN {pos_sents_list}""")
        tokens_list = [list(row) for row in self.cur.fetchall()]
        print(tokens_list)


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
