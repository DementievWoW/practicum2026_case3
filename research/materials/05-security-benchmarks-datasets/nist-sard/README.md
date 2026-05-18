# NIST SARD (Software Assurance Reference Dataset)

- **Status:** verified
- **Тип:** dataset
- **Канонический URL:** https://samate.nist.gov/SARD/
- **Год / venue / CVE-ID:** Поддерживается NIST SAMATE; пополняемый ресурс

## Что это
Растущая коллекция тестовых программ с задокументированными уязвимостями, поддерживаемая командой NIST SAMATE. По данным официальной страницы — более 450 000 тест-кейсов (от малых сниппетов до полноценных приложений) на C, C++, Java, PHP и C#, покрывающих более 150 классов CWE. Используется разработчиками SAST/инструментов безопасности для калибровки и пользователями — для выбора подходящих инструментов оценки. (В случае это «известный реальный ресурс»; проверено по https://samate.nist.gov/SARD/.)

## Почему релевантно
Пул помеченных уязвимых/безопасных программ, включая CWE-89 (SQL Injection), полезен для построения и валидации судьи: даёт ground truth для обучения/тестирования компонентов, оценивающих риск SQL-инъекций и других классов уязвимостей вокруг работы с базами данных.

## README-превью (для GitHub) или ключевые поля CVE (для CVE)
Официальная формулировка: «SARD is a growing collection of test programs with documented weaknesses». NIST позиционирует ресурс как помощь «tool developers ... and users seeking suitable tools». Покрытие: 5 языков (C, C++, Java, PHP, C#), 150+ CWE-классов, 450 000+ тест-кейсов.

## Источник
- WebFetch'нуто: 2026-05-18, URL https://samate.nist.gov/SARD/
- Цитаты: «more than 450,000 test cases»; «more than 150 Common Weakness Enumeration classes (CWE)»; «a growing collection of test programs with documented weaknesses».
