# PythonShazam
## Использование и установка
1) Установка заключается в копировании файлов с гитхаба и запуска `$ pip install requirements.txt`

2) Запустите `$ make clean reset` чтобы очистить и заново инициализировать базу данных

3) Запустите `$ make tests` чтобы убедиться, что всё правильно сконфигурировано

4) Скопируйте любые .mp3 аудио файлы в директорию `mp3/`

5) Запустите $ make fingerprint-songs для анализа файлов и добавления их в базу данных

6) Включите любой файл из директории(в любом приложении) `mp3/`, и параллельно запустите `$ make recognize-listen seconds=5`

7) Для удаления какой-либо одной песни запустите 

`$ python sql-execute.py -q "DELETE FROM songs WHERE id = 6;"`
`$ python sql-execute.py -q "DELETE FROM fingerprints WHERE song_fk = 6;"`

(вместо id и song_fk своё значение)
