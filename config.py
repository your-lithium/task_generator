def data_choicemaker():
    def choice_input():
        chosen_mode = input("Введіть 1, якщо Ви хочете використовувати вже наявні тексти.\n"
                            "Введіть 2, якщо Ви хочете використати власний текст і внести його до бази даних.\n"
                            "Введіть 3, якщо Ви хочете використати власний текст без внесення його до бази даних.\n")
        if chosen_mode not in "123":
            print("Невірний формат відповіді. Будь ласка, спробуйте ще раз.")
            chosen_mode = data_choicemaker()

        return chosen_mode

    mode = choice_input()
    if mode == "1":
        import pandas as pd
        from ast import literal_eval
        read_data = pd.read_csv("pronouns.csv", sep=";", quotechar="\\", encoding="windows-1251", header=0,
                                dtype={"word_number": int, "pronoun": str},
                                converters={"sentence": literal_eval, "variants": literal_eval})
        data_lines = [list(row) for row in read_data.values]
    elif mode == "2":
        data_lines = dbworker(textworker())
    else:
        data_lines = textworker()

    return data_lines


def textworker():
    def filename_input():
        filename = input("Введіть назву свого файлу або повний шлях до нього:\n")
        try:
            with open(filename, "r", encoding="windows-1251") as f:
                read_text = f.read()
        except IOError:
            print("Вибачте, такого файлу не існує. Спробуйте ще раз.")
            read_text = textworker()

        return read_text

    text = filename_input()
    from nltk.tokenize import sent_tokenize
    try:
        sentences_list = sent_tokenize(text)
    except LookupError:
        from nltk import download
        download('punkt')
        sentences_list = sent_tokenize(text)
    del text

    import pymorphy2
    morph = pymorphy2.MorphAnalyzer(lang="uk")
    from re import findall

    def analysis(sentence):
        word_list = findall("[\w']+|[\(\)\.!?:,—\;]", sentence)
        pronoun_list = []
        for j in range(len(word_list)-1):
            try:
                if {"Fixd"} not in morph.parse(word_list[j])[0].tag:
                    if morph.parse(word_list[j])[0].tag.POS == "NPRO":
                        p = morph.parse(word_list[j])[0]
                    elif morph.parse(word_list[j])[1].tag.POS == "NPRO":
                        p = morph.parse(word_list[j])[1]
                    else:
                        continue
                else:
                    for h in range(len(morph.parse(word_list[j]))):
                        if {"Fixd"} in morph.parse(word_list[j])[h].tag:
                            continue
                        else:
                            if morph.parse(word_list[j])[h].tag.POS == "NPRO":
                                p = morph.parse(word_list[j])[h]
                                break
                            else:
                                continue
                    else:
                        continue
            except IndexError:
                continue

            cases = [{"nomn"}, {"gent"}, {"datv"}, {"accs"}, {"loct"}]
            try:
                variants = []
                for q in cases:
                    word_case = p.inflect(q).word
                    if word_case not in variants and word_case != word_list[j].lower():
                        variants.append(word_case)

                if word_list[j].lower() != word_list[j]:
                    for k in range(len(variants)):
                        variants[k] = variants[k].capitalize()

                pronoun_list.append([j, word_list, word_list[j], variants])
            except AttributeError:
                continue

        del word_list
        return pronoun_list

    analysed = []
    for i in sentences_list:
        i_analysis = analysis(i)
        if i_analysis is not None:
            for q in i_analysis:
                analysed.append(q)

    del morph
    del sentences_list
    return analysed


def dbworker(analysed, filename="pronouns.csv"):
    import pandas as pd
    from ast import literal_eval

    read_data = pd.read_csv(filename, sep=";", quotechar="\\", encoding="windows-1251", header=0,
                            dtype={"word_number": int, "pronoun": str},
                            converters={"sentence": literal_eval, "variants": literal_eval})
    rows = [list(row) for row in read_data.values]

    new_rows = []
    for i in analysed:
        if i in rows:
            continue
        else:
            new_rows.append(i)

    new_data = pd.DataFrame(new_rows, columns=["word_number", "sentence", "pronoun", "variants"])
    new_data.to_csv(filename, sep=";", quotechar="\\", encoding="windows-1251", header=0, mode="a", index=False)

    data = rows + new_rows
    return data


def taskmaker(data_lines):
    def quantity_chooser(quantity_lines):
        try:
            quantity_input = int(input("Введіть бажану кількість питань. Наразі доступно: {}.\n".format(quantity_lines)))
            if quantity_input > len(data_lines):
                quantity_input = len(data_lines)
                print("На жаль, такої кількості питань не має в наявності. Буде надано: {}.".format(quantity_input))
            else:
                return quantity_input
        except ValueError:
            print("Невірний формат відповіді; приймаються виключно цілі числа. Будь ласка, спробуйте ще раз.")
            quantity_input = quantity_chooser(quantity_lines)

        return quantity_input

    # def grading_choicemaker():
    #     grading = input("Введіть 1, якщо Ви хочете отримувати правильні відповіді одразу після завдань.\n"
    #                     "Введіть 2, якщо Ви хочете отримувати відповіді одразу після завдань, а також оцінку наприкінці.\n"
    #                     "Введіть 3, якщо Ви хочете отримувати оцінку та правильні відповіді наприкінці.\n")
    #     if grading not in "123":
    #         print("Невірний формат відповіді. Будь ласка, спробуйте ще раз.")
    #         grading_choicemaker()
    #     return grading

    quantity = quantity_chooser(len(data_lines))

    from random import sample, shuffle
    random_lines = sample(data_lines, k=quantity)
    del data_lines

    from re import fullmatch
    from ast import literal_eval

    for i in random_lines:
        number = int(i[0])
        if type(i[1]) is not list:
            sentence = literal_eval(i[1])
        else:
            sentence = i[1]
        correct = i[2]

        question = ""
        for j in range(len(sentence)):
            word = sentence[j]
            if j != number:
                if fullmatch("[\w']+|[—\)\.,:;]", word) and j+1 != len(sentence) \
                        and sentence[j+1] not in ".!?,:;)":
                    question += word + " "
                else:
                    question += word
            else:
                question += "___ "

        if type(i[3]) is not list:
            variants = literal_eval(i[3])
        else:
            variants = i[3]
        variants = sample(variants, k=2)
        variants.append(correct)
        shuffle(variants)
        users = input("{}\nA)  {}\nБ)  {}\nВ)  {}\n".format(question, variants[0], variants[1], variants[2]))
