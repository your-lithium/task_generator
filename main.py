"""Автоматичне укладання вправ із граматики української мови як іноземної"""

import stanza
import sqlite3
import customtkinter as tk
from tkinter import ttk
import tkinter.filedialog as filedialog
import random
from collections import defaultdict
import re
import pymorphy3

# узгодження назв доступних частин мови в англійській та українській
pos_ukrainian_mapping = {"іменник": "noun",
                         "займенник": "pronoun"}

# узгодження позначень частин мови stanza і pymorphy з позначеннями БД
pos_name_mapping = {'ADJ': 'adjective',
                    'ADP': 'adposition',
                    'ADV': 'adverb',
                    'AUX': 'verb',
                    'CCONJ': 'conjunction',
                    'DET': 'determiner',
                    'INTJ': 'interjection',
                    'NOUN': 'noun',
                    'NUM': 'number',
                    'PART': 'particle',
                    'PRON': 'pronoun',
                    'PROPN': 'proper_noun',
                    'PUNCT': 'punct',
                    'SCONJ': 'conjunction',
                    'SYM': 'symbol',
                    'VERB': 'verb',
                    'X': 'foreign',
                    'ADJF': 'adjective',
                    'ADJS': 'adjective',
                    'COMP': 'adverb',
                    'INFN': 'verb',
                    'PRTF': 'adjective',
                    'PRTS': 'adjective',
                    'GRND': 'verb',
                    'NUMR': 'number',
                    'ADVB': 'adverb',
                    'NPRO': 'pronoun',
                    'PRED': 'adverb',
                    'PREP': 'adposition',
                    'CONJ': 'conjunction',
                    'PRCL': 'particle'
                    }

# узгодження позначень морфологічних категорій pymorphy3 i stanza з позначеннями БД
gender_mapping = {'Masc': 'masculine',
                  'masc': 'masculine',
                  'Fem': 'feminine',
                  'femn': 'feminine',
                  'Neut': 'neutral',
                  'neut': 'neutral'}
number_mapping = {'Sing': 'singular',
                  'sing': 'singular',
                  'Plur': 'plural',
                  'plur': 'plural'}
person_mapping = {'1': 1,
                  '1per': 1,
                  '2': 2,
                  '2per': 2,
                  '3': 3,
                  '3per': 3}

# узгодження позначень відмінків pymorphy3 з позначеннями БД і stanza
case_mapping = {'nomn': 'nom',
                'gent': 'gen',
                'datv': 'dat',
                'accs': 'acc',
                'ablt': 'ins',
                'loct': 'loc',
                'voct': 'voc',
                'gen2': 'gen',
                'acc2': 'acc',
                'loc2': 'loc'}


class SQL:
    """Містить SQL-запити та методи створення БД вправ."""

    @staticmethod
    def choose_tasks(level: int, pos: str, set_number: int) -> list[list]:
        """Створює список вправ, які підходять під вимоги користувача"""

        # отримати список словоформ потрібного рівня
        cur.execute(f"""SELECT *
                        FROM {pos}_level
                        WHERE level_id = {level}""")
        level_list = [[description[0] for description in cur.description[1:]][i]
                      for i, boolean in enumerate(cur.fetchall()[0][1:]) if boolean == 1]

        # отримати список цільових слів за частиною мови та рівнем
        cur.execute(f"""SELECT text, sentence_id, token_index, {", ".join(level_list)}
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
                        WHERE sentence_id IN
                                (SELECT sentence_id
                                FROM token
                                WHERE pos = '{pos}'
                                    AND sentence_id IN
                                        (SELECT sentence_id
                                        FROM sentence_set
                                        WHERE set_id = {set_number}))
                            AND (pos != '{pos}'
                                OR (pos = '{pos}'
                                    AND (form NOT IN {tuple(level_list)}
                                        OR form IS NULL)))
                            """)
        stems_list = [list(row) for row in cur.fetchall()]

        # почистити стрижні-дублікати
        stems = defaultdict(list)
        stems_numbers = {correct[1] for correct in corrects_list}
        for sent_id in stems_numbers:
            stems[sent_id] = [correct[:1] + correct[2:] for correct in corrects_list if correct[1] == sent_id]
            if len(stems[sent_id]) > 1:
                selected = random.sample(stems[sent_id], 1)
                rejected = [item[:1] + item[1:2] for item in stems[sent_id] if item != selected[0]]
                stems[sent_id] = selected
                stems[sent_id].extend(rejected)
            stems[sent_id].extend([item[:1] + item[2:] for item in stems_list if item[1] == sent_id])

        stems = list(stems.values())
        return stems

    @staticmethod
    def add_tasks(task_set: list[str], sentences: dict[str, list[dict[str, str | int | dict[str, str | int] | None]]]) \
            -> None:
        """Додає новий користувацький набір вправ у БД"""

        # вставити дані про новий набір вправ
        cur.execute(f"""INSERT INTO "set" (name, description)
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
                # noinspection PyUnboundLocalVariable
                cur.execute(f"""INSERT INTO sentence_set
                                VALUES ('{sentence_id}', '{set_id}')""")
                con.commit()

    @staticmethod
    def add_tokens(tokens: list[dict[str, str | int | dict[str, str | int] | None]], sentence_id: int) -> None:
        """Додає слова із речень у БД"""
        for token in tokens:

            # перевірити, чи цільова частина мови (має вказану форму)
            if token['form']:
                query = f"""SELECT {token['pos']}_id
                            FROM {token['pos']}
                            WHERE {token['form']} = '{token['text'].lower()}'
                                AND """
                for k, v in token['features'].items():
                    if v:
                        query += f"{k} = '{v}' AND "
                    else:
                        query += f"{k} IS NULL AND "
                query = query[:-5]
                cur.execute(query)

                # перевірити наявність леми у таблиці
                try:
                    pos_id = cur.fetchall()[0][0]

                # леми нема у БД: додати її
                except IndexError:
                    pos_id = SQL.add_pos(token['pos'], token['forms'], token['features'])

            # нецільова частина мови: не прив'язувати до таблиці
            else:
                pos_id = None

            # вставити токени у таблицю
            query = """INSERT INTO token (text, sentence_id, token_index, pos, pos_id, form)
                            VALUES (?, ?, ?, ?, ?, ?)"""
            values = (token['text'], sentence_id, token['token_index'], token['pos'], pos_id, token['form'])
            cur.execute(query, values)

    @staticmethod
    def add_pos(pos: str, forms: dict[str, str], features: dict[str, str]) -> int:
        """Додає нову лему у БД"""
        # отримати список колонок і значень форм і граматичних категорій
        feature_columns = list(features.keys())
        feature_values = list(features.values())
        form_columns = list(forms.keys())
        form_values = list(forms.values())
        columns = tuple(form_columns + feature_columns)
        values = tuple(form_values + feature_values)

        # вставити дані про леми у таблицю
        cur.execute(f"""INSERT INTO {pos} {columns}
                        VALUES {values}""".replace('None', 'NULL'))
        cur.execute(f"""SELECT seq
                        FROM sqlite_sequence
                        WHERE name = '{pos}'""")
        pos_id = cur.fetchall()[0][0]

        return pos_id

    @staticmethod
    def get_levels():
        """Витягує список рівнів"""
        cur.execute("SELECT level_id, name FROM level")
        results = {}
        for level_id, name in cur.fetchall():
            results[name] = level_id
        return results

    @staticmethod
    def get_sets():
        """Витягує список наборів вправ з описами"""
        cur.execute("SELECT set_id, name, description FROM 'set'")
        results = {}
        for set_id, name, description in cur.fetchall():
            results[name] = set_id, description
        return results

    @staticmethod
    def check_sets(task_set_name: str) -> bool:
        """З'ясовує, чи існує набір із заданою назвою"""
        cur.execute(f"SELECT 1 FROM 'set' WHERE name = '{task_set_name}' LIMIT 1")
        if len(cur.fetchall()) == 0:
            return False
        return True


class Token:
    """Обробляє слова із користувацького тексту"""

    def __init__(self, token_doc):
        self.token_doc = token_doc
        self.text = token_doc.text
        self.index = token_doc.id - 1
        self.pos = None
        self.get_pos()
        self.form = None
        self.get_form()
        self.forms = None
        self.get_forms()
        self.features = None
        self.get_features()

    def get_pos(self):
        self.pos = pos_name_mapping[self.token_doc.upos]

    def get_form(self):
        pass

    def get_forms(self):
        pass

    def get_features(self):
        pass

    def get_dict(self):
        return {'text': self.text, 'token_index': self.index, 'pos': self.pos, 'form': self.form, 'forms': self.forms,
                'features': self.features}


class Pronoun(Token):
    """Обробляє займенники із користувацького тексту"""

    def __init__(self, token_doc):
        self.doc_forms = {}
        self.doc_features = {key: value for [key, value] in [pair.split('=')
                                                             for pair in token_doc.feats.split('|')]}
        super().__init__(token_doc)

    def get_pos(self):
        self.pos = 'pronoun'

    def get_form(self):
        self.form = self.doc_features['Case'].lower()

    def get_forms(self):
        lemmas = morph.parse(self.text)
        for i in lemmas:
            if pos_name_mapping[i.tag.POS] == self.pos and case_mapping[i.tag.case] == self.form:
                lemma = i
                break
            lemma = lemmas[0]

        try:
            # noinspection PyUnboundLocalVariable
            self.forms = {'nom': lemma.inflect({'nomn'}).word,
                          'gen': lemma.inflect({'gent'}).word,
                          'dat': lemma.inflect({'datv'}).word,
                          'acc': lemma.inflect({'accs'}).word,
                          'ins': lemma.inflect({'ablt'}).word,
                          'loc': lemma.inflect({'loct'}).word}
        except AttributeError:
            self.form = None
            self.forms = None

    def get_features(self):
        try:
            gender = gender_mapping[self.doc_features['Gender']]
        except KeyError:
            gender = None

        try:
            number = number_mapping[self.doc_features['Number']]
        except KeyError:
            number = None

        try:
            person = person_mapping[self.doc_features['Person']]
        except KeyError:
            person = None

        self.features = {'gender': gender, 'number': number, 'person': person}

    def get_dict(self):
        return super().get_dict()


class Noun(Token):
    """Обробляє іменники із користувацького тексту"""

    def __init__(self, token_doc):
        self.doc_forms = {}
        self.doc_features = {key: value for [key, value] in [pair.split('=')
                                                             for pair in token_doc.feats.split('|')]}
        super().__init__(token_doc)

    def get_pos(self):
        self.pos = 'noun'

    def get_form(self):
        self.form = self.doc_features['Case'].lower()
        self.form += '_s' if self.doc_features['Number'] == 'Sing' else '_p'

    def get_forms(self):
        lemmas = morph.parse(self.text)
        for i in lemmas:
            if (i.tag.POS is not None and pos_name_mapping.get(i.tag.POS) == self.pos and
                    ((case_mapping.get(i.tag.case) is not None and case_mapping.get(i.tag.case) in self.form) or
                     (i.tag.case is None and self.form == 'nom_s')) and
                    'Pltm' not in i.tag and
                    'Name' not in i.tag and
                    'Surn' not in i.tag and
                    'Patr' not in i.tag):
                lemma = i.normalized
                break
        else:
            lemma = lemmas[0].normalized

        try:
            self.forms = {'nom_s': lemma.inflect({'nomn'}).word,
                          'gen_s': lemma.inflect({'gent'}).word,
                          'dat_s': lemma.inflect({'datv'}).word,
                          'acc_s': lemma.inflect({'accs'}).word,
                          'ins_s': lemma.inflect({'ablt'}).word,
                          'loc_s': lemma.inflect({'loct'}).word,
                          'voc_s': lemma.inflect({'voct'}).word,
                          'nom_p': lemma.inflect({'plur', 'nomn'}).word,
                          'gen_p': lemma.inflect({'plur', 'gent'}).word,
                          'dat_p': lemma.inflect({'plur', 'datv'}).word,
                          'acc_p': lemma.inflect({'plur', 'accs'}).word,
                          'ins_p': lemma.inflect({'plur', 'ablt'}).word,
                          'loc_p': lemma.inflect({'plur', 'loct'}).word,
                          'voc_p': lemma.inflect({'plur', 'voct'}).word}
        except AttributeError:
            self.form = None
            self.forms = None

    def get_features(self):
        try:
            gender = gender_mapping[self.doc_features['Gender']]
        except KeyError:
            gender = None

        self.features = {'gender': gender}

    def get_dict(self):
        return super().get_dict()


class Pluralia(Token):
    """Обробляє pluralia tantum із користувацького тексту"""

    def __init__(self, token_doc):
        super().__init__(token_doc)

    def get_pos(self):
        self.pos = 'pluralia'

    def get_dict(self):
        return super().get_dict()


class ProperNoun(Token):
    """Обробляє власні назви із користувацького тексту"""

    def __init__(self, token_doc):
        super().__init__(token_doc)

    def get_pos(self):
        self.pos = 'proper_noun'

    def get_dict(self):
        return super().get_dict()


class Text:
    """Обробляє користувацький текст"""

    pos_class_mapping = {'PRON': Pronoun,
                         'NOUN': Noun}

    def __init__(self, file_path: str, task_set: list[str]):
        self.set = task_set
        self.text = None
        self.sentences = {}
        self.read_text(file_path)
        self.clean_text()
        nlp = stanza.Pipeline("uk")
        self.doc = nlp(self.text)
        self.analyse_text()

    def read_text(self, file_path: str) -> None:
        """Зчитує текст із файлу"""
        with open(file_path, encoding="utf-8") as file:
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
        con.commit()


class Sentence(Text):
    """Обробляє речення із користувацького тексту"""

    # noinspection PyMissingConstructor
    def __init__(self, sentence_doc: stanza.models.common.doc.Sentence):
        self.sentence_doc = sentence_doc
        self.text = sentence_doc.text
        self.tokens = []
        self.analyse_tokens()

    def analyse_tokens(self):
        for token in self.sentence_doc.words:
            if token.upos == "PROPN":
                self.tokens.append(ProperNoun(token).get_dict())
            elif token.feats and ('Ptan' in token.feats or ('Plur' in token.feats and 'Gender' not in token.feats)):
                self.tokens.append(Pluralia(token).get_dict())
            elif token.upos in self.pos_class_mapping and 'Ptan' not in token.feats:
                token_instance = self.pos_class_mapping[token.upos](token)
                self.tokens.append(token_instance.get_dict())
            else:
                self.tokens.append(Token(token).get_dict())

    def get_dict(self):
        return {self.text: self.tokens}


class Spinbox(tk.CTkFrame):
    """Створює віджет Spinbox"""
    def __init__(self, *args,
                 width: int = 150,
                 height: int = 32,
                 step_size: int = 1,
                 max_value: int,
                 **kwargs):
        super().__init__(*args, width=width, height=height, **kwargs)

        self.step_size = step_size
        self.command = None
        self.max_value = max_value

        self.configure(fg_color=("gray78", "gray28"))  # set frame color

        self.grid_columnconfigure(0, weight=0)  # buttons don't expand
        self.grid_columnconfigure(2, weight=0)  # buttons don't expand
        self.grid_columnconfigure(1, weight=1)  # entry expands

        self.subtract_button = tk.CTkButton(self, text="-", width=height - 6, height=height - 6,
                                            command=self.subtract_button_callback)
        self.subtract_button.grid(row=0, column=0, padx=(3, 0), pady=3)

        self.entry = tk.CTkEntry(self, width=width - (2 * height), height=height - 6, border_width=0)
        self.entry.grid(row=0, column=1, columnspan=1, padx=3, pady=3, sticky="ew")

        self.add_button = tk.CTkButton(self, text="+", width=height - 6, height=height - 6,
                                       command=self.add_button_callback)
        self.add_button.grid(row=0, column=2, padx=(0, 3), pady=3)

        # default value
        self.entry.insert(0, 0)

    def add_button_callback(self):
        if self.command is not None:
            self.command()
        try:
            if int(self.entry.get()) < self.max_value:
                value = int(self.entry.get()) + self.step_size
                self.entry.delete(0, "end")
                self.entry.insert(0, value)
        except ValueError:
            return

    def subtract_button_callback(self):
        if self.command is not None:
            self.command()
        try:
            if int(self.entry.get()) > 0:
                value = int(self.entry.get()) - self.step_size
                self.entry.delete(0, "end")
                self.entry.insert(0, value)
        except ValueError:
            return

    def get(self) -> [int | None]:
        try:
            return int(self.entry.get())
        except ValueError:
            return None

    def set(self, value: float):
        self.entry.delete(0, "end")
        self.entry.insert(0, str(int(value)))


class Messagebox(tk.CTkToplevel):
    """Створює віконце з повідомленням"""
    def __init__(self, title: str, text: str) -> None:
        super().__init__()
        self.title(title)
        self.resizable(False, False)

        self.frame = tk.CTkFrame(self)
        self.frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        text_label = tk.CTkLabel(self.frame, text=text, font=("Helvetica", 14), wraplength=300)
        text_label.grid(row=0, column=0, pady=(20, 5), padx=20)

        button = tk.CTkButton(self.frame, text="OK", font=("Helvetica", 12), command=self.destroy)
        button.grid(row=1, column=0, pady=(5, 20), padx=20)

        self.focus_force()
        self.grab_set()

    def destroy(self):
        self.grab_release()
        super().destroy()


# noinspection PyBroadException
class Body(tk.CTkFrame):
    """Формує тіло інтерфейсу"""

    def __init__(self, master, *args, **kwargs):
        super().__init__(master, *args, **kwargs)

        # визначити потрібні змінні
        self.correct = None
        self.distractors = None
        self.task = None
        self.results = None
        self.toplevel_window = None
        self.task_num = None
        self.answer_mapping = None
        self.answers = None
        self.task_section = None
        self.task_iter = None
        self.selected_value = None
        self.quantity_entry = None
        self.set_values = None
        self.level_values = None
        self.tasks = None
        self.set_dropdown = None
        self.pos_dropdown = None
        self.level_dropdown = None
        self.name_entry = None
        self.description_entry = None
        self.file_path = None

        # визначити параметри шрифтів
        self.font_head = ("Helvetica", 14, "bold")
        self.font_label = ("Helvetica", 14)
        self.font_button = ("Helvetica", 12)

        # запустити початковий екран
        self.starting_screen()

    def starting_screen(self):
        """Створює початковий екран"""
        # очистити вікно
        for widget in self.winfo_children():
            widget.destroy()

        # створити заголовок
        top_label_text = "Вітаємо у застосунку автоматичного укладання вправ\n" \
                         "із граматики української мови як іноземної!"
        top_label = tk.CTkLabel(self, text=top_label_text, font=self.font_head)
        top_label.grid(row=0, column=0, columnspan=2, pady=20, padx=20)

        # створити розділювачі
        separator_line = ttk.Separator(self, orient=tk.HORIZONTAL)
        separator_line.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        # створити ліву секцію
        left_section = tk.CTkFrame(self)
        left_section.grid(row=2, column=0, padx=(10, 5), pady=10, sticky="nsew")

        left_label_text = "Розпочніть тестування \nіз наявними вправами"
        left_label = tk.CTkLabel(left_section, text=left_label_text, font=self.font_label, wraplength=200,
                                 justify=tk.CENTER)
        left_label.pack(pady=(20, 5), padx=10, anchor="center")

        left_button = tk.CTkButton(left_section, text="Розпочати", font=self.font_button)
        left_button.pack(pady=(5, 20), padx=10, anchor="center")
        left_button.configure(command=self.configure_testing)

        # створити праву секцію
        right_section = tk.CTkFrame(self)
        right_section.grid(row=2, column=1, padx=(5, 10), pady=10, sticky="nsew")

        right_label_text = "Створіть нові вправи\nіз своїх текстів"
        right_label = tk.CTkLabel(right_section, text=right_label_text, font=self.font_label, wraplength=200,
                                  justify=tk.CENTER)
        right_label.pack(pady=(20, 5), padx=10, anchor="center")

        right_button = tk.CTkButton(right_section, text="Створити", font=self.font_button)
        right_button.pack(pady=(5, 20), padx=10, anchor="center")
        right_button.configure(command=self.upload_tasks)

        # здійснити конфігурацію колонок
        self.grid_columnconfigure(1)

    def configure_testing(self):
        """Запускає тестування"""
        # очистити вікно
        for widget in self.winfo_children():
            widget.destroy()

        # поставити кнопку повернення назад
        back_button = tk.CTkButton(self, text="🡨", command=self.starting_screen, font=self.font_button, width=30)
        back_button.grid(row=0, column=0, sticky='w', pady=10, padx=10)

        # створити віджети для вибору рівня, частини мови та набору вправ
        header_label = tk.CTkLabel(self, text="Оберіть параметри для подальшого тестування", font=self.font_head)
        header_label.grid(row=1, column=0, sticky='w', pady=(0, 10), padx=10)

        level_label = tk.CTkLabel(self, text="Оберіть бажаний рівень для вправ:", font=self.font_label)
        level_label.grid(row=2, column=0, sticky='w', pady=(0, 5), padx=10)
        self.level_values = SQL.get_levels()
        self.level_dropdown = tk.CTkComboBox(self, values=list(self.level_values.keys()))
        self.level_dropdown.grid(row=3, column=0, sticky='w', pady=(0, 10), padx=10)

        separator_line1 = ttk.Separator(self, orient=tk.HORIZONTAL)
        separator_line1.grid(row=4, column=0, sticky="ew", pady=10)
        self.grid_rowconfigure(4)

        pos_label = tk.CTkLabel(self, text="Оберіть цільову частину мови:", font=self.font_label)
        pos_label.grid(row=5, column=0, sticky='w', pady=(0, 5), padx=10)
        pos_values = list(pos_ukrainian_mapping.keys())
        self.pos_dropdown = tk.CTkComboBox(self, values=pos_values)
        self.pos_dropdown.grid(row=6, column=0, sticky='w', pady=(0, 10), padx=10)

        separator_line2 = ttk.Separator(self, orient=tk.HORIZONTAL)
        separator_line2.grid(row=7, column=0, sticky="ew", pady=10)
        self.grid_rowconfigure(7)

        set_label = tk.CTkLabel(self, text="Оберіть потрібний набір вправ:", font=self.font_label)
        set_label.grid(row=8, column=0, sticky='w', pady=(0, 5), padx=10)
        self.set_values = SQL.get_sets()
        self.set_dropdown = tk.CTkComboBox(self, values=list(self.set_values.keys()))
        self.set_dropdown.grid(row=9, column=0, sticky='w', pady=(0, 10), padx=10)

        separator_line3 = ttk.Separator(self, orient=tk.HORIZONTAL)
        separator_line3.grid(row=10, column=0, sticky="ew", pady=10)
        self.grid_rowconfigure(10)

        process_button = tk.CTkButton(self, text="Завантажити вправи", command=self.get_tasks, font=self.font_button)
        process_button.grid(row=11, column=0, sticky='ew', pady=10, padx=10)

    def get_tasks(self):
        """Обирає із БД потрібні вправи"""
        # отримати дані про обрані вправи та завантажити їх
        selected_level = self.level_values.get(self.level_dropdown.get())
        selected_pos = pos_ukrainian_mapping.get(self.pos_dropdown.get())
        selected_set = self.set_values.get(self.set_dropdown.get())[0]
        self.tasks = SQL.choose_tasks(selected_level, selected_pos, selected_set)

        # очистити вікно
        for widget in self.winfo_children():
            widget.destroy()

        # поставити кнопку повернення назад
        back_button = tk.CTkButton(self, text="🡨", command=self.configure_testing, font=self.font_button, width=30)
        back_button.grid(row=0, column=0, sticky='w', pady=(0, 10), padx=10)

        # створити віджети для вибору кількості вправ
        header_label = tk.CTkLabel(self, text="Оберіть бажану кількість вправ для тестування", font=self.font_head)
        header_label.grid(row=1, column=0, sticky='w', pady=10, padx=10)

        quantity_label = tk.CTkLabel(self, text=f"Доступно {len(self.tasks)} вправ.", font=self.font_label)
        quantity_label.grid(row=2, column=0, sticky='w', pady=(0, 5), padx=10)
        self.quantity_entry = Spinbox(self, max_value=len(self.tasks))
        self.quantity_entry.grid(row=3, column=0, sticky='w', pady=(0, 10), padx=10)

        separator_line1 = ttk.Separator(self, orient=tk.HORIZONTAL)
        separator_line1.grid(row=4, column=0, sticky="ew", pady=10)
        self.grid_rowconfigure(4)

        process_button = tk.CTkButton(self, text="Розпочати тестування", command=self.start_testing,
                                      font=self.font_button)
        process_button.grid(row=5, column=0, sticky='ew', pady=10, padx=10)

    def start_testing(self):
        """Здійснює тестування"""
        self.task_num = int(self.quantity_entry.get())
        try:
            self.tasks = random.sample(self.tasks, self.task_num)
        except ValueError:
            Messagebox("Недостатньо вправ", f"На жаль, така кількість вправ не доступна. Оберіть {len(self.tasks)}"
                                            f" або менше вправ.")
        else:
            # очистити вікно
            for widget in self.winfo_children():
                widget.destroy()

            # додати основні елементи
            task_label = tk.CTkLabel(self, text="Оберіть пропущене слово.", font=self.font_label)
            task_label.grid(row=0, column=0, sticky='w', pady=(0, 5), padx=10)

            # додати елементи завдань
            self.task_iter = iter(self.tasks)
            self.answers = []
            self.results = []
            self.task_section = tk.CTkFrame(self)
            self.task_section.grid(row=1, column=0, sticky="nsew", padx=10)
            self.play_task()

            # додати основні елементи
            next_button = tk.CTkButton(self, text="Зберегти відповідь", command=self.play_task,
                                       font=self.font_button)
            next_button.grid(row=2, column=0, sticky='ew', pady=10, padx=10)

    def play_task(self):
        """Заповнює завдання і забирає відповіді"""
        try:
            # забрати попередню відповідь
            self.answers.append(self.answer_mapping.get(self.selected_value.get()))
        except AttributeError:
            pass
        else:
            if not self.answers[-1]:
                self.results.append([self.task, self.correct, self.selected_value.get()])

        try:
            i = next(self.task_iter)
        except StopIteration:
            # якщо завдання закінчились:
            self.show_results()
        else:
            # очистити рамку
            for widget in self.task_section.winfo_children():
                widget.destroy()

            # створити віджети завдання
            self.task = self.make_task(i)
            stem_label = tk.CTkLabel(self.task_section, text=self.task, font=self.font_head)
            stem_label.grid(row=0, column=0, sticky='w', pady=10, padx=10)

            self.correct = i[0][0].lower()
            self.distractors = [j for j in i[0][2:] if j != i[0][0].lower()]
            self.distractors = random.sample(self.distractors, 2)
            self.distractors.append(self.correct)
            self.answer_mapping = {self.correct: True,
                                   self.distractors[0]: False,
                                   self.distractors[1]: False}
            random.shuffle(self.distractors)

            self.selected_value = tk.StringVar()
            for j, distractor in enumerate(self.distractors):
                pady_value = (0, 5)
                if j == len(self.distractors) - 1:
                    pady_value = (0, 15)

                radio_button = tk.CTkRadioButton(self.task_section, text=distractor, variable=self.selected_value,
                                                 value=distractor, font=self.font_label)
                radio_button.grid(row=j + 1, column=0, sticky='w', pady=pady_value, padx=10)

    @staticmethod
    def make_task(tokens: list[list]) -> str:
        """Створює текст для речень"""
        # впорядкувати токени
        tokens_sorted = []
        for i in range(len(tokens)):
            for j in tokens:
                if j[1] == i:
                    tokens_sorted.append(j)

        question = ""
        for i, token in enumerate(tokens_sorted):
            # перевірити, чи цільове слово
            if len(token) > 2:
                text = "___"
            else:
                text = token[0]

            # додати пробіл перед токеном, якщо треба
            if len(question) != 0 and re.fullmatch(r"[(—«\w].*", text):
                question += " "

            # доєднати слово
            question += text

        return question

    def show_results(self):
        """Показує результати проходження тестування"""
        for widget in self.winfo_children():
            widget.destroy()

        result_label = tk.CTkLabel(self, font=self.font_head,
                                   text=f"Правильна відповідь на {self.answers.count(True)} із {self.task_num} вправ.")
        result_label.grid(row=0, column=0, pady=(20, 5), padx=20)

        if len(self.results) > 0:
            show_mistakes_button = tk.CTkButton(self, text="Переглянути помилки",
                                                command=self.show_mistakes, font=self.font_button)
            show_mistakes_button.grid(row=1, column=0, pady=5, padx=20)
            starting_screen_button = tk.CTkButton(self, text="Завершити тестування",
                                                  command=self.starting_screen, font=self.font_button)
            starting_screen_button.grid(row=2, column=0, pady=(5, 20), padx=20)
        else:
            starting_screen_button = tk.CTkButton(self, text="Завершити тестування",
                                                  command=self.starting_screen, font=self.font_button)
            starting_screen_button.grid(row=1, column=0, pady=(5, 20), padx=20)

    def show_mistakes(self):
        """Показує список помилок із виправленнями"""
        if self.toplevel_window is None or not self.toplevel_window.winfo_exists():
            self.toplevel_window = tk.CTkToplevel(self)
            self.toplevel_window.title("Результати")
            self.toplevel_window.resizable(False, False)
            self.toplevel_window.grab_set()

            results_frame = tk.CTkFrame(self.toplevel_window)
            results_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
            results_frame.grid_columnconfigure(0, minsize=250)

            for i, mistake in enumerate(self.results):
                task = mistake[0]
                correct = mistake[1]
                answer = mistake[2]
                pady_value = (10, 0)
                if i == len(self.results) - 1:
                    pady_value = 10

                mistake_frame = tk.CTkFrame(results_frame)
                mistake_frame.grid(row=i, column=0, sticky="ew", padx=10, pady=pady_value)
                mistake_frame.grid_columnconfigure(0, minsize=250)

                task_label = tk.CTkLabel(mistake_frame, text=task, font=self.font_head)
                task_label.grid(row=0, column=0, sticky='w', pady=(10, 0), padx=10)
                correct_label = tk.CTkLabel(mistake_frame, text=f"Правильна відповідь: {correct}", font=self.font_label)
                correct_label.grid(row=1, column=0, sticky='w', pady=0, padx=10)
                answer_label = tk.CTkLabel(mistake_frame, text=f"Ваша відповідь: {answer}", font=self.font_label)
                answer_label.grid(row=2, column=0, sticky='w', pady=(0, 10), padx=10)
        else:
            self.toplevel_window.focus()

    def upload_tasks(self):
        """Дозволяє завантажити свої тексти у БД"""
        # очистити вікно
        for widget in self.winfo_children():
            widget.destroy()

        # поставити кнопку повернення назад
        back_button = tk.CTkButton(self, text="🡨", command=self.starting_screen, font=self.font_button, width=30)
        back_button.grid(row=0, column=0, sticky='w', pady=10, padx=10)

        # створити віджети
        header_label = tk.CTkLabel(self, text="Внесіть потрібні дані про новий набір вправ", font=self.font_head)
        header_label.grid(row=1, column=0, columnspan=2, sticky='w', pady=(0, 10), padx=10)

        name_label = tk.CTkLabel(self, text="Введіть бажану назву набору:", font=self.font_label)
        name_label.grid(row=2, column=0, columnspan=2, sticky='w', pady=(0, 5), padx=(10, 5))
        self.name_entry = tk.CTkEntry(self, font=self.font_label)
        self.name_entry.grid(row=3, column=0, sticky='ew', pady=(0, 10), padx=10)
        name_button = tk.CTkButton(self, text="Переглянути зайняті", command=self.show_names, font=self.font_button)
        name_button.grid(row=3, column=1, sticky='ew', pady=(0, 10), padx=(5, 10))

        separator_line1 = ttk.Separator(self, orient=tk.HORIZONTAL)
        separator_line1.grid(row=4, column=0, columnspan=2, sticky="ew", pady=10)
        self.grid_rowconfigure(4)

        description_label = tk.CTkLabel(self, text="Введіть опис нового набору:", font=self.font_label)
        description_label.grid(row=5, column=0, columnspan=2, sticky='w', pady=(0, 5), padx=10)
        self.description_entry = tk.CTkEntry(self, font=self.font_label)
        self.description_entry.grid(row=6, column=0, columnspan=2, sticky='ew', pady=(0, 10), padx=10)

        separator_line2 = ttk.Separator(self, orient=tk.HORIZONTAL)
        separator_line2.grid(row=7, column=0, columnspan=2, sticky="ew", pady=10)
        self.grid_rowconfigure(7)

        file_label = tk.CTkLabel(self, text="Оберіть файл із вашим текстом:", font=self.font_label)
        file_label.grid(row=8, column=0, columnspan=2, sticky='w', pady=(0, 5), padx=10)
        file_button = tk.CTkButton(self, text="Вибрати файл", command=self.choose_file, font=self.font_button)
        file_button.grid(row=9, column=0, sticky='w', pady=(0, 10), padx=10)

        separator_line3 = ttk.Separator(self, orient=tk.HORIZONTAL)
        separator_line3.grid(row=10, column=0, columnspan=2, sticky="ew", pady=10)
        self.grid_rowconfigure(10)

        process_button = tk.CTkButton(self, text="Завантажити вправи", command=self.process_tasks,
                                      font=self.font_button)
        process_button.grid(row=11, column=0, columnspan=2, sticky='ew', pady=10, padx=10)

    def show_names(self):
        """Показує вже зайняті назви наборів з їхніми описами"""
        if self.toplevel_window is None or not self.toplevel_window.winfo_exists():
            sets = SQL.get_sets()
            if len(sets) > 0:
                self.toplevel_window = tk.CTkToplevel(self)
                self.toplevel_window.title("Зайняті назви наборів")
                self.toplevel_window.resizable(False, False)
                self.toplevel_window.grab_set()

                for i in sets.items():
                    set_name = i[0]
                    set_id = i[1][0]
                    set_description = i[1][1]
                    pady_value = (10, 0)
                    if set_id == len(sets.items()):
                        pady_value = 10

                    set_frame = tk.CTkFrame(self.toplevel_window)
                    set_frame.grid(row=set_id - 1, column=0, sticky="nsew", padx=10, pady=pady_value)
                    set_frame.grid_columnconfigure(0, minsize=250)
                    name_label = tk.CTkLabel(set_frame, text=set_name, font=self.font_head)
                    name_label.grid(row=0, column=0, sticky='w', pady=(10, 0), padx=10)
                    description_label = tk.CTkLabel(set_frame, text=set_description, font=self.font_label)
                    description_label.grid(row=1, column=0, sticky='w', pady=(0, 10), padx=10)
            else:
                Messagebox("Зайняті назви наборів", "Всі назви вільні. Створюйте перший набір!")
        else:
            self.toplevel_window.focus()

    def choose_file(self):
        """Дозволяє отримати шлях до файлу із текстом для вправ"""
        self.file_path = filedialog.askopenfilename()

    def process_tasks(self):
        """Обробляє завантажені дані"""
        if SQL.check_sets(self.name_entry.get()) is False:
            if self.file_path:
                try:
                    Text(self.file_path, [self.name_entry.get(), self.description_entry.get()])
                except TypeError:
                    Messagebox("Пусті поля", "Заповніть, будь ласка, всі поля.")
                except Exception:
                    Messagebox("Помилка", "Сталася помилка. Будь ласка, спробуйте знову.")
                else:
                    Messagebox("Успіх!", "Було успішно укладено завдання із вашого тексту.")
                    self.starting_screen()
            else:
                Messagebox("Не обраний файл", "Оберіть, будь ласка, файл із вашим текстом.")
        else:
            Messagebox("Зайнята назва", "На жаль, ця назва набору зайнята. Будь ласка, спробуйте іншу.")


class Application(tk.CTk):
    """Представляє інтерфейс програми"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.title("Вправи із граматики")
        self.grid_rowconfigure(0, weight=1)  # configure grid system
        self.grid_columnconfigure(0, weight=1)
        self.resizable(False, False)

        self.my_frame = Body(master=self)
        self.my_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")


if __name__ == '__main__':
    con = sqlite3.connect('tasks.db')
    cur = con.cursor()
    morph = pymorphy3.MorphAnalyzer(lang='uk')
    app = Application()
    app.mainloop()
    con.close()
