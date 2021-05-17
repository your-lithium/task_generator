def textworker():
    def filename_input():
        filename = input("\nВведіть назву файлу зі своїм текстом або повний шлях до нього:\n")
        try:
            with open(filename, "r", encoding="windows-1251") as f:
                read_text = f.read()
        except IOError:
            print("Вибачте, такого файлу не існує. Спробуйте ще раз.")
            read_text = filename_input()

        return read_text

    text = filename_input()
    from nltk.tokenize import sent_tokenize
    try:
        sentences_list = list(set(sent_tokenize(text)))
    except LookupError:
        from nltk import download
        download('punkt')
        sentences_list = list(set(sent_tokenize(text)))

    import pymorphy2
    morph = pymorphy2.MorphAnalyzer(lang="uk")
    from re import findall

    a1_ok = ["я", "ми", "ти", "ви", "він", "вона", "воно", "вони",
             "мій", "моя", "моє", "мої", "твій", "твоя", "твоє", "твої",
             "наш", "наша", "наше", "наші", "ваш", "ваша", "ваше", "ваші",
             "їхній", "їхня", "їхнє", "їхні",
             "той", "та", "те", "ті", "цей", "ця", "це", "ці"]

    def analysis(sentence):
        sentence = sentence.strip('"')
        word_list = findall("[\w']+|[\(\)\.!?:,—\;]", sentence)
        pronoun_list = []
        for j, word in enumerate(word_list):
            try:
                for parse in morph.parse(word):
                    if {"Fixd"} in parse.tag or parse.tag.POS != "NPRO":
                        continue
                    if parse.normalized.word.lower() in a1_ok and parse.tag.case != "ablt":
                        p = parse
                        break
                    continue
                else:
                    continue
            except IndexError:
                continue

            cases = [{"nomn"}, {"gent"}, {"datv"}, {"accs"}, {"loct"}]
            try:
                variants = []
                for s in cases:
                    word_case = p.inflect(s).word
                    if word_case not in variants and word_case != word.lower():
                        variants.append(word_case)

                if word.lower() != word:
                    for k, variant in enumerate(variants):
                        variants[k] = variant.capitalize()

                pronoun_list.append([j, word_list, word, variants])
            except AttributeError:
                continue

        return pronoun_list

    analysed = []
    for i in sentences_list:
        i_analysis = analysis(i)
        if i_analysis is not None:
            for q in i_analysis:
                analysed.append(q)

    return analysed


def dbworker(analysed):
    def db_chooser():
        chosen_filename = input(
            "\nЯкщо ви НЕ хочете користуватися стандартною базою даних pronouns.csv, введіть назву файлу з вашою БД.\n"
            "Якщо ви хочете користуватися стандартною БД, натисніть Enter.\n")
        if chosen_filename == "":
            chosen_filename = "pronouns.csv"

        if isfile(chosen_filename) is not True:
            print("Некоректна назва файлу. Будь ласка, спробуйте ще раз.")
            chosen_filename = db_chooser()

        return chosen_filename

    from os.path import isfile
    filename = db_chooser()
    import pandas as pd
    from ast import literal_eval

    try:
        read_data = pd.read_csv(filename, sep=";", quotechar="\\", encoding="windows-1251", header=0,
                                dtype={"word_number": int, "pronoun": str},
                                converters={"sentence": literal_eval, "variants": literal_eval})
        rows = [list(row) for row in read_data.values]

        new_rows = []
        for i in analysed:
            if i in rows:
                continue
            new_rows.append(i)

        new_data = pd.DataFrame(new_rows, columns=["word_number", "sentence", "pronoun", "variants"])
        new_data.to_csv(filename, sep=";", quotechar="\\", mode="a",
                        encoding="windows-1251", header=0, index=False)
        data = rows + new_rows

    except pd.errors.EmptyDataError:
        new_data = pd.DataFrame(analysed, columns=["word_number", "sentence", "pronoun", "variants"])
        new_data.to_csv(filename, sep=";", quotechar="\\", mode="a",
                        encoding="windows-1251", index=False,
                        header=["word_number", "sentence", "pronoun", "variants"])
        data = [list(row) for row in new_data.values]

    return data


def task_grading_executor():
    def data_choicemaker():
        def choice_input():
            chosen_mode = input("Введіть 1, якщо Ви хочете використовувати вже наявні тексти.\n"
                                "Введіть 2, якщо Ви хочете використати свій текст і внести його до бази даних.\n"
                                "Введіть 3, якщо Ви хочете використати свій текст без внесення його до бази даних.\n")
            if chosen_mode not in "123":
                print("Невірний формат відповіді. Будь ласка, спробуйте ще раз.\n")
                chosen_mode = choice_input()

            return chosen_mode

        mode = choice_input()
        if mode == "1":
            import pandas as pd
            from ast import literal_eval
            read_data = pd.read_csv("pronouns.csv", sep=";", quotechar="\\", encoding="windows-1251", header=0,
                                    dtype={"word_number": int, "pronoun": str},
                                    converters={"sentence": literal_eval, "variants": literal_eval})
            chosen_data = [list(row) for row in read_data.values]
        elif mode == "2":
            chosen_data = dbworker(textworker())
        else:
            chosen_data = textworker()

        return chosen_data

    def quantity_choicemaker(quantity_lines):
        try:
            chosen_quantity = int(
                input("\nВведіть бажану кількість питань. Наразі доступно: {}.\n".format(quantity_lines)))
            if chosen_quantity > quantity_lines:
                chosen_quantity = quantity_lines
                print("На жаль, такої кількості питань не має в наявності. Буде надано: {}.\n".format(chosen_quantity))
            else:
                return chosen_quantity
        except ValueError:
            print("Невірний формат відповіді; приймаються виключно цілі числа. Будь ласка, спробуйте ще раз.")
            chosen_quantity = quantity_choicemaker(quantity_lines)

        return chosen_quantity

    data_lines = data_choicemaker()
    quantity = quantity_choicemaker(len(data_lines))

    from random import sample, shuffle
    random_lines = sample(data_lines, k=quantity)

    from re import fullmatch
    from ast import literal_eval

    def task_maker(line):
        number = int(line[0])
        if type(line[1]) is not list:
            sentence_list = literal_eval(line[1])
        else:
            sentence_list = line[1]
        correct = line[2]

        question = ""
        for j, word in enumerate(sentence_list):
            if j != number:
                if fullmatch("[\w']+|[—\)\.,:;]", word) and j + 1 != len(sentence_list) \
                        and sentence_list[j + 1] not in ".!?,:;)":
                    question += word + " "
                else:
                    question += word
            else:
                question += "___ "

        if type(line[3]) is not list:
            variants = literal_eval(line[3])
        else:
            variants = line[3]
        variants = sample(variants, k=2)
        variants.append(correct)
        shuffle(variants)

        correct_index = variants.index(correct)
        if correct_index == 0:
            correct_letter = "А"
        elif correct_index == 1:
            correct_letter = "Б"
        else:
            correct_letter = "В"

        users = input(
            "\n{}\nA)  {}\nБ)  {}\nВ)  {}\n".format(question, variants[0], variants[1], variants[2])).capitalize()

        if users not in "АБВ":
            print("Вибачте, ви ввели відповідь у некоректному форматі. Будь ласка, спробуйте ще раз.")
            correct, users, correct_letter, question = task_maker(line)
            print()

        return correct, users, correct_letter, question

    def grading_choicemaker():
        chosen_grading = input("\nВведіть 1, якщо Ви хочете отримувати правильні відповіді одразу після завдань.\n"
                               "Введіть 2, якщо Ви хочете отримувати відповіді одразу після завдань, а також оцінку наприкінці.\n"
                               "Введіть 3, якщо Ви хочете отримувати оцінку та правильні відповіді наприкінці.\n")
        if chosen_grading not in "123":
            print("Невірний формат відповіді. Будь ласка, спробуйте ще раз.")
            chosen_grading = grading_choicemaker()

        return chosen_grading

    grading = grading_choicemaker()

    if grading == "1":
        for i in random_lines:
            correct_answer = task_maker(i)[0]
            print(correct_answer)

        input()

    elif grading == "2":
        correct_quantity = 0

        for i in random_lines:
            correct_word, answer, correct_answer = task_maker(i)[:-1]
            print("Правильна відповідь: {}.\n".format(correct_word))
            if answer == correct_answer:
                correct_quantity += 1

        percentage = correct_quantity / quantity * 100
        print("\nВи виконали {} з {} завдань правильно. Процент правильних відповідей: {}%".format(correct_quantity,
                                                                                                   quantity,
                                                                                                   percentage))
        input()

    else:
        correct_quantity = 0
        incorrect_dict = {}

        for i in random_lines:
            correct_word, answer, correct_answer, sentence = task_maker(i)
            if answer == correct_answer:
                correct_quantity += 1
            else:
                incorrect_dict[sentence] = correct_word

        if incorrect_dict != {}:
            print("\nВаша відповідь була неправильною у таких реченнях:")
        for k, v in incorrect_dict.items():
            print('У реченні "{}" мав бути займенник "{}".'.format(k, v))

        percentage = correct_quantity / quantity * 100
        print("\nВи виконали {} з {} завдань правильно. Процент правильних відповідей: {}%".format(correct_quantity,
                                                                                                   quantity,
                                                                                                   percentage))

    input("Натисніть Enter, щоб зупинити програму (можливо, зачиниться вікно програми).")
