# task_generator

***(English below)***

Невеличкий проект, що має на меті автоматичну генерацію вправ про займенники з декількома варіантами відповіді для вивчення української мови як іноземної.
Найкраще підходить для рівня володіння українською А1.

Для початку роботи запустіть `task_generator.py`.
`pronouns.csv` — файл з БД вправ за замовчанням: 457 вправ.
`test1` — файл, усі речення з якого присутні у БД; невеликий, для тестингу роботи додавання вправ без повторень; 23 речення, з них мають додаватися до БД 0 (0 вправ).
`test2` — файл, деякі речення з якого присутні у БД; невеликий, для тестингу роботи додавання вправ без повторень; 12 речень, з них мають додаватися до БД 10 (11 вправ).
`test3` — файл, на якому будується БД; великий, використовувати у випадку, коли БД було очищено; 586 речень.
`config.py` — файл з конфігурацією програми.

Існує можливість роботи з наявною базою даних вправ, робота з новим матеріалом від користувача (у вигляді тексту), а також його додавання до БД.
Користувач може обирати кількість вправ, з якою він хоче працювати, а також тип перевірки за двома параметрами (правильне рішення одразу після питання/наприкінці та підрахунок балів та відсотку правильних відповідей наприкінці/без підрахунку результату).
Наразі проблеми є тільки з займенником "тому" (у БД 7 вправ, де визначився як займенник омонімічний сполучник).

Для початку роботи може знадобитися встановлення таких бібліотек для **Python 3.x**, як: `pandas` (та `numpy`), `pymorphy2` (та `pymorphy2-dicts-uk`), `nltk`.
Без участі останніх двох може працювати лише 1 функція — генерація вправ на основі даних існуючої БД.
Для роботи `nltk` повинно бути встановленим середовище **Microsoft Visual C++**.

Щодо будь-яких питань можна звертатися у [Telegram](t.me/your_lithium)!

ฅ^•ﻌ•^ฅ



A little project aimed at generating multiple-choice questions for learning Ukrainian pronouns from simple text.
Best suited for A1 level of fluency in Ukrainian.

Run `task_generator.py` to start.
`pronouns.csv` — the default DB file: 457 exercises.
`test1` — the file all of the sentences in which are in the DB; small, used to test omitting the duplicates; 23 sentences, of which 0 have to add (0 exercises).
`test2` — the file a few sentences of which are in the DB; small, used to test omitting the duplicates; 12 sentences, of which 10 have to add (11 exercises).
`test3` — the file with all of the sentences DB is built on; large, used in case DB has been cleared; 586 sentences.
`config.py` — configuration file.

Users can work with the existing database of exercises, initiate the generation of new ones based on their own text data and add them to the DB.
There are options of choosing the number of questions to work with and the type of control by two parameters (the correct solution immediately after answering/at the end and points and percentage of correct answers calculation/no score calculation).

You may need to have installed those **Python 3.x** modules for the program to work correctly: `pandas` (and `numpy`), `pymorphy2` (and `pymorphy2-dicts-uk`), `nltk`.
Without the last two, only the 1st feature will work — exercise generation from the existing DB.
You have to have the **Microsoft Visual C++** compiler installed for `nltk` to work.

Feel free to message me in [Telegram](t.me/your_lithium) for any questions!

ฅ^•ﻌ•^ฅ
