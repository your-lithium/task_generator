"""Автоматичне укладання вправ із граматики української мови як іноземної"""

import stanza
import sqlite3
import tkinter as tk
from tkinter import ttk
import tkinter.filedialog as filedialog
from tkinter import messagebox
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
                    'PROPN': 'noun',
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

        global con
        global cur

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

        global con
        global cur

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
            else:
                lemma = lemmas[0]

        self.forms = {'nom': lemma.inflect({'nomn'}).word,
                      'gen': lemma.inflect({'gent'}).word,
                      'dat': lemma.inflect({'datv'}).word,
                      'acc': lemma.inflect({'accs'}).word,
                      'ins': lemma.inflect({'ablt'}).word,
                      'loc': lemma.inflect({'loct'}).word}

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
            if pos_name_mapping[i.tag.POS] == self.pos \
                    and (case_mapping.get(i.tag.case) is not None and case_mapping.get(i.tag.case) in self.form) or (
                    i.tag.case is None and self.form == 'nom_s') \
                    and {'Pltm'} not in i.tag:
                lemma = i.normalized
                break
            else:
                lemma = lemmas[0].normalized

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
        con.commit()


class Sentence(Text):
    """Обробляє речення із користувацького тексту"""

    def __init__(self, sentence_doc: stanza.models.common.doc.Sentence):
        self.sentence_doc = sentence_doc
        self.text = sentence_doc.text
        self.tokens = []
        self.analyse_tokens()

    def analyse_tokens(self):
        for token in self.sentence_doc.words:
            if token.upos in self.pos_class_mapping and 'Ptan' not in token.feats:
                token_instance = self.pos_class_mapping[token.upos](token)
                self.tokens.append(token_instance.get_dict())
            elif token.feats and 'Ptan' in token.feats:
                self.tokens.append(Pluralia(token).get_dict())
            else:
                self.tokens.append(Token(token).get_dict())

    def get_dict(self):
        return {self.text: self.tokens}


class Body(tk.Frame):
    """Формує тіло інтерфейсу"""

    def __init__(self, master, *args, **kwargs):
        super().__init__(master, *args, **kwargs)

        # визначити параметри шрифтів
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
        self.font_head = ("Helvetica", 12, "bold")
        self.font_label = ("Helvetica", 12)
        self.font_button = ("Helvetica", 10)

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
        top_label = tk.Label(self, text=top_label_text, font=self.font_head)
        top_label.grid(row=0, column=0, columnspan=3, pady=10)

        # створити розділювачі
        separator_line = ttk.Separator(self, orient=tk.HORIZONTAL)
        separator_line.grid(row=1, column=0, columnspan=3, sticky="ew", pady=10)
        separator_vertical = ttk.Separator(self, orient=tk.VERTICAL)
        separator_vertical.grid(row=2, column=1, rowspan=2, sticky="ns", padx=10)

        # створити ліву секцію
        left_section = tk.Frame(self)
        left_section.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")

        left_label_text = "Розпочніть тестування \nіз наявними вправами"
        left_label = tk.Label(left_section, text=left_label_text, font=self.font_label, wraplength=200,
                              justify=tk.CENTER)
        left_label.pack(pady=(20, 5), padx=10, anchor="center")

        left_button = tk.Button(left_section, text="Розпочати", font=self.font_button, fg="white", bg="black")
        left_button.pack(pady=(5, 20), padx=10, anchor="center")
        left_button.configure(command=self.configure_testing)

        # створити праву секцію
        right_section = tk.Frame(self)
        right_section.grid(row=2, column=2, padx=10, pady=10, sticky="nsew")

        right_label_text = "Створіть нові вправи\nіз своїх текстів"
        right_label = tk.Label(right_section, text=right_label_text, font=self.font_label, wraplength=200,
                               justify=tk.CENTER)
        right_label.pack(pady=(20, 5), padx=10, anchor="center")

        right_button = tk.Button(right_section, text="Створити", font=self.font_button, fg="white", bg="black")
        right_button.pack(pady=(5, 20), padx=10, anchor="center")
        right_button.configure(command=self.upload_tasks)

        # здійснити конфігурацію колонок
        self.grid_columnconfigure(1)

    def configure_testing(self):
        """Запускає тестування"""

        # очистити вікно
        for widget in self.winfo_children():
            widget.destroy()

        # створити віджети для вибору рівня, частини мови та набору вправ
        header_label = tk.Label(self, text="Оберіть параметри для подальшого тестування", font=self.font_head)
        header_label.grid(row=0, column=0, sticky='w', pady=10)

        level_label = tk.Label(self, text="Оберіть бажаний рівень для вправ:", font=self.font_label)
        level_label.grid(row=1, column=0, sticky='w', pady=(0, 5))
        self.level_values = SQL.get_levels()
        self.level_dropdown = ttk.Combobox(self, values=list(self.level_values.keys()))
        self.level_dropdown.grid(row=2, column=0, sticky='w', pady=(0, 10))

        separator_line1 = ttk.Separator(self, orient=tk.HORIZONTAL)
        separator_line1.grid(row=3, column=0, sticky="ew", pady=10)
        self.grid_rowconfigure(3)

        pos_label = tk.Label(self, text="Оберіть цільову частину мови:", font=self.font_label)
        pos_label.grid(row=4, column=0, sticky='w', pady=(0, 5))
        pos_values = list(pos_ukrainian_mapping.keys())
        self.pos_dropdown = ttk.Combobox(self, values=pos_values)
        self.pos_dropdown.grid(row=5, column=0, sticky='w', pady=(0, 10))

        separator_line2 = ttk.Separator(self, orient=tk.HORIZONTAL)
        separator_line2.grid(row=6, column=0, sticky="ew", pady=10)
        self.grid_rowconfigure(6)

        set_label = tk.Label(self, text="Оберіть потрібний набір вправ:", font=self.font_label)
        set_label.grid(row=7, column=0, sticky='w', pady=(0, 5))
        self.set_values = SQL.get_sets()
        self.set_dropdown = ttk.Combobox(self, values=list(self.set_values.keys()))
        self.set_dropdown.grid(row=8, column=0, sticky='w', pady=(0, 10))

        separator_line3 = ttk.Separator(self, orient=tk.HORIZONTAL)
        separator_line3.grid(row=9, column=0, sticky="ew", pady=10)
        self.grid_rowconfigure(9)

        process_button = tk.Button(self, text="Завантажити вправи", command=self.get_tasks, font=self.font_button,
                                   fg="white", bg="black")
        process_button.grid(row=10, column=0, sticky='ew', pady=(0, 10))

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

        # створити віджети для вибору кількості вправ
        header_label = tk.Label(self, text="Оберіть бажану кількість вправ для тестування", font=self.font_head)
        header_label.grid(row=0, column=0, sticky='w', pady=10)

        quantity_label = tk.Label(self, text=f"Доступно {len(self.tasks)} вправ.", font=self.font_label)
        quantity_label.grid(row=1, column=0, sticky='w', pady=(0, 5))
        self.quantity_entry = tk.Spinbox(self, from_=1, to=len(self.tasks), font=self.font_label)
        self.quantity_entry.grid(row=2, column=0, sticky='w', pady=(0, 10))

        separator_line1 = ttk.Separator(self, orient=tk.HORIZONTAL)
        separator_line1.grid(row=3, column=0, sticky="ew", pady=10)
        self.grid_rowconfigure(3)

        process_button = tk.Button(self, text="Розпочати тестування", command=self.start_testing, font=self.font_button,
                                   fg="white", bg="black")
        process_button.grid(row=4, column=0, sticky='ew', pady=(0, 10))

    def start_testing(self):
        """Здійснює тестування"""

        task_num = int(self.quantity_entry.get())
        self.tasks = random.sample(self.tasks, task_num)

        # self.task_iter = iter(self.tasks)
        # i = next(self.task_iter)
        for i in self.tasks:
            # додати основні елементи
            task_label = tk.Label(self, text="Оберіть пропущене слово.", font=self.font_label)
            task_label.grid(row=0, column=0, sticky='w', pady=(0, 5))

            separator_line1 = ttk.Separator(self, orient=tk.HORIZONTAL)
            separator_line1.grid(row=1, column=0, sticky="ew", pady=10)
            self.grid_rowconfigure(1)

            # додати елементи завдань
            task_section = tk.Frame(self)
            task_section.grid(row=2, column=0, sticky="nsew")

            stem_label = tk.Label(task_section, text=self.make_task(i), font=self.font_head)
            stem_label.grid(row=0, column=0, sticky='w', pady=10)

            distractors = [j for j in i[0][2:] if j != i[0][0].lower()]
            distractors = random.sample(distractors, 2)
            distractors.append(i[0][0].lower())
            self.selected_value = tk.StringVar()
            for j, distractor in enumerate(distractors):
                radio_button = tk.Radiobutton(task_section, text=distractor, variable=self.selected_value, value=distractor,
                                              font=self.font_label)
                radio_button.grid(row=j + 1, column=0, sticky='w', pady=(0, 5))

            # додати основні елементи
            separator_line2 = ttk.Separator(self, orient=tk.HORIZONTAL)
            separator_line2.grid(row=3, column=0, sticky="ew", pady=10)
            self.grid_rowconfigure(3)

            next_button = tk.Button(self, text="Зберегти відповідь", command=self.save_answer(),
                                    font=self.font_button,
                                    fg="white", bg="black")
            next_button.grid(row=4, column=0, sticky='ew', pady=(0, 10))

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
            if len(question) != 0 and re.fullmatch(r"[\(—«\w\d].*", text):
                question += " "

            # доєднати слово
            question += text

        return question

    def save_answer(self):
        # очистити вікно
        for widget in self.winfo_children():
            widget.destroy()

    def upload_tasks(self):
        """Дозволяє завантажити свої тексти у БД"""

        # очистити вікно
        for widget in self.winfo_children():
            widget.destroy()

        # створити віджети
        header_label = tk.Label(self, text="Внесіть потрібні дані про новий набір вправ", font=self.font_head)
        header_label.grid(row=0, column=0, sticky='w', pady=10)

        name_label = tk.Label(self, text="Введіть бажану назву набору:", font=self.font_label)
        name_label.grid(row=1, column=0, sticky='w', pady=(0, 5))
        self.name_entry = tk.Entry(self, font=self.font_label)
        self.name_entry.grid(row=2, column=0, sticky='w', pady=(0, 10))

        separator_line1 = ttk.Separator(self, orient=tk.HORIZONTAL)
        separator_line1.grid(row=3, column=0, sticky="ew", pady=10)
        self.grid_rowconfigure(3)

        description_label = tk.Label(self, text="Введіть опис нового набору:", font=self.font_label)
        description_label.grid(row=4, column=0, sticky='w', pady=(0, 5))
        self.description_entry = tk.Entry(self, font=self.font_label)
        self.description_entry.grid(row=5, column=0, columnspan=2, sticky='ew', pady=(0, 10))

        separator_line2 = ttk.Separator(self, orient=tk.HORIZONTAL)
        separator_line2.grid(row=6, column=0, sticky="ew", pady=10)
        self.grid_rowconfigure(6)

        file_label = tk.Label(self, text="Оберіть файл із вашим текстом:", font=self.font_label)
        file_label.grid(row=7, column=0, sticky='w', pady=(0, 5))
        file_button = tk.Button(self, text="Вибрати файл", command=self.choose_file, font=self.font_button, fg="white",
                                bg="black")
        file_button.grid(row=8, column=0, sticky='w', pady=(0, 10))

        separator_line3 = ttk.Separator(self, orient=tk.HORIZONTAL)
        separator_line3.grid(row=9, column=0, sticky="ew", pady=10)
        self.grid_rowconfigure(9)

        process_button = tk.Button(self, text="Завантажити вправи", command=self.process_tasks, font=self.font_button,
                                   fg="white", bg="black")
        process_button.grid(row=10, column=0, sticky='ew', pady=(0, 10))

    def choose_file(self):
        """Дозволяє отримати шлях до файлу із текстом для вправ"""
        self.file_path = filedialog.askopenfilename()

    def process_tasks(self):
        """Обробляє завантажені дані"""
        Text(self.file_path, [self.name_entry.get(), self.description_entry.get()])
        messagebox.showinfo("Success", "Tasks processed successfully!")
        self.starting_screen()


class Application(tk.Tk):
    """Представляє інтерфейс програми"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.title("Вправи із граматики")
        self.body = Body(self, padx=15, pady=15)
        self.body.pack()


if __name__ == '__main__':
    con = sqlite3.connect('tasks.db')
    cur = con.cursor()
    morph = pymorphy3.MorphAnalyzer(lang='uk')
    app = Application()
    app.mainloop()
    con.close()
