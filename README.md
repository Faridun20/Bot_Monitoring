# Telegram userbot для автопостинга в свои группы

Постит 2 раза в день одинаковые/чередующиеся сообщения **с твоего личного
аккаунта** (через Telethon / User API) в список твоих же групп. Работает как
long-running процесс — на Railway или на своей VPS (например, Oracle Cloud
Free Tier) через systemd.

## Что это и зачем

- Объём: 2 поста в день × ~5–20 своих групп.
- Постинг идёт с **твоего личного аккаунта**, не от бота — для аудитории это
  важно.
- Это не массовая рассылка. Скрипт делает то же, что делает человек в клиенте
  Telegram — просто по расписанию, с человеческими задержками и jitter'ом.

## Локальная разработка

1. Получи `API_ID` и `API_HASH` на <https://my.telegram.org> → API development
   tools.
2. Создай виртуальное окружение и установи зависимости:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # macOS/Linux:
   source .venv/bin/activate
   pip install -r requirements-dev.txt
   ```
3. Скопируй `.env.example` → `.env`, заполни `API_ID`, `API_HASH`,
   `TARGET_GROUPS`, `DRAFTS_SOURCE`, `SCHEDULE`, `TIMEZONE`.
   Подробнее про `DRAFTS_SOURCE` — в разделе [«Добавление и редактирование
   постов»](#добавление-и-редактирование-постов).
4. Сгенерируй `SESSION_STRING` (один раз, локально):
   ```bash
   python scripts/generate_session.py
   ```
   Telegram спросит телефон, код из приложения и (если включена) 2FA.
   Скрипт распечатает длинную строку — это и есть `SESSION_STRING`. Скопируй её
   в `.env`.
5. Прогон локально для проверки:
   ```bash
   python -m src.main
   ```
   В логах должно появиться `Authorized as ...` и
   `Scheduler started: [(10, 0), (19, 30)] (Asia/Tashkent)`.
6. Чтобы проверить отправку без ожидания — временно подставь в `SCHEDULE` время
   через минуту-другую, например `SCHEDULE=14:23`, и поставь
   `JITTER_MINUTES=0`.

## Деплой на Railway

1. Залей репозиторий на GitHub (без `.env` и без сессионных файлов — `.gitignore`
   их и так не пропустит).
2. На <https://railway.app> → New Project → Deploy from GitHub repo → выбери
   репозиторий.
3. В `Variables` сервиса добавь все обязательные переменные:
   - `API_ID`
   - `API_HASH`
   - `SESSION_STRING` (та самая длинная строка, полученная локально)
   - `TARGET_GROUPS`
   - `DRAFTS_SOURCE`
   - `SCHEDULE`
   - `TIMEZONE`
   - при необходимости — опциональные (`DRAFTS_SCAN_LIMIT`, `ACTIVE_TAG`,
     `DELAY_BETWEEN_GROUPS_MIN/MAX`, `JITTER_MINUTES`, `MAX_SLOW_MODE_WAIT`,
     `SHUFFLE_GROUPS`, `LOG_LEVEL`).
4. Service автоматически стартует как worker (`Procfile: worker: python -m src.main`).
5. Логи: Railway dashboard → проект → Deployments → View Logs. Должны увидеть:
   ```
   Authorized as <твоё имя> (@<username>) id=...
   Scheduler started: [(10, 0), (19, 30)] (Asia/Tashkent), groups=N
   ```
6. **Healthcheck не нужен** — это worker, не web-сервис.

## Деплой на Oracle Cloud Free Tier (VPS)

В отличие от Railway это настоящая машина: она не передеплоивается сама по
`git push` и не перезапускает упавший процесс сама по себе. Оба момента
закрывает systemd.

### 1. Создать инстанс

- Oracle Cloud Console → Compute → Instances → **Create Instance**.
- Image: Ubuntu 22.04 или 24.04 (входит в Always Free).
- Shape: любой Always Free — `VM.Standard.A1.Flex` (ARM) или
  `VM.Standard.E2.1.Micro` (AMD). Все зависимости проекта — чистый Python,
  архитектура значения не имеет.
- Добавь свой SSH-ключ при создании инстанса.
- Сеть трогать не нужно: бот не принимает входящие соединения (только
  исходящие к серверам Telegram), поэтому кроме порта 22 (SSH, открыт по
  умолчанию) ничего открывать не требуется.

### 2. Подключиться и подготовить окружение

```bash
ssh ubuntu@<PUBLIC_IP>

sudo apt update && sudo apt install -y python3 python3-venv git

git clone https://github.com/Faridun20/Bot_Monitoring.git
cd Bot_Monitoring

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Заполнить `.env`

```bash
cp .env.example .env
nano .env       # заполни как локально: API_ID, API_HASH, SESSION_STRING,
                 # TARGET_GROUPS, DRAFTS_SOURCE, SCHEDULE, TIMEZONE
chmod 600 .env   # секреты — читать может только владелец файла
```

`config.py` подхватывает `.env` из текущей директории точно так же, как при
локальном запуске — на VPS ничего доопределять не нужно.

### 4. Запустить как systemd-сервис

В репозитории уже лежит шаблон [`userbot.service`](userbot.service).

```bash
sudo cp userbot.service /etc/systemd/system/
sudo nano /etc/systemd/system/userbot.service   # поправь User= и пути, если
                                                  # клонировал не в
                                                  # /home/ubuntu/Bot_Monitoring
sudo systemctl daemon-reload
sudo systemctl enable --now userbot
```

`enable` — чтобы бот поднимался сам после перезагрузки сервера. `Restart=on-failure`
в юните — чтобы перезапускался при падении (аналог `restartPolicyType` в Railway).

### 5. Логи

```bash
sudo journalctl -u userbot -f
```

Должно быть то же самое, что и локально: `Authorized as ...`,
`Scheduler started: ...`.

### 6. Обновление

Посты — как обычно, через drafts-канал, без каких-либо действий на сервере.
Если поменялся код:

```bash
cd ~/Bot_Monitoring
git pull
source .venv/bin/activate && pip install -r requirements.txt   # если requirements.txt менялся
sudo systemctl restart userbot
```

### ⚠️ Не запускай бота в двух местах одновременно

Если переезжаешь с Railway на Oracle — **останови или удали Railway-сервис**
перед стартом на VPS. Оба процесса используют один и тот же `SESSION_STRING`
и независимо друг от друга поднимут свой `AsyncIOScheduler` — в 10:00/19:30
пост уйдёт **дважды** в каждую группу.

## Добавление и редактирование постов

Источник постов — **приватный Telegram-канал**, в который пишешь только ты.
Никаких коммитов и деплоев для изменения текстов не требуется.

### Один раз

1. Создай приватный канал в Telegram (например, «My Bot Drafts»). Подписан в
   нём только ты.
2. Узнай его `@username` (если публичный) или числовой ID. Для приватного
   канала без username: перешли любое сообщение из него боту
   [@username_to_id_bot](https://t.me/username_to_id_bot) или
   [@JsonDumpBot](https://t.me/JsonDumpBot) — они вернут ID вида
   `-1001234567890`.
3. Положи это значение в `DRAFTS_SOURCE` (локально в `.env`; на проде — в
   Railway → Variables или в `.env` на сервере).

### Каждый день

- **Добавить пост в ротацию** — отправь обычное сообщение в этот канал. Текст,
  фото, видео, GIF, документ, **альбом из нескольких фото/видео одним
  сообщением** — что угодно, что умеет Telethon. В конце добавь хэштег
  `#active`. Если это альбом — тег можно оставить в подписи любого фото
  альбома, все фото/видео из него уйдут вместе, одним сообщением.
- **Убрать пост из ротации** — отредактируй сообщение, убери `#active`.
  Само сообщение остаётся в канале как архив.
- **Изменить пост** — просто отредактируй сообщение, изменения подхватятся
  при следующей плановой рассылке.
- **Посмотреть, что сейчас в ротации** — открой канал, найди сообщения с
  `#active`.

Userbot перед каждой плановой рассылкой читает последние
`DRAFTS_SCAN_LIMIT=500` сообщений канала, фильтрует те, где есть `#active`, и
выбирает одно случайное. Хэштег-маркер из текста перед отправкой вырезается.
Если канал пуст / нет ни одного помеченного сообщения — в логе будет
`Skip broadcast: ...`, бот не падает, ждёт следующего слота.

Если хочется другой маркер вместо `#active` — задай `ACTIVE_TAG=#другой`.

### Несколько активных постов и расписание

Если в ротации несколько `#active`-постов, бот не шлёт их все разом одной
пачкой (это выглядело бы как явный спам-паттерн), а каждый раз выбирает один.
При этом он **не повторяет тот же пост, что ушёл прошлым разом** — если
активных постов больше одного, следующая рассылка гарантированно возьмёт
другой.

Чтобы посты уходили не только в 10:00 и 19:30, а чаще (например, с разницей
в полчаса) — просто добавь ещё времена в `SCHEDULE`, без каких-либо
доработок кода:
```
SCHEDULE=10:00,10:30,19:30,20:00
```
Каждый слот — это отдельная полноценная рассылка по всем `TARGET_GROUPS` с
собственным jitter'ом и задержками между группами. Учитывай: больше слотов
в день = больше суммарного объёма сообщений на каждую группу, а именно объём
— главный фактор риска бана (см. «Безопасность» ниже). Добавляй частоту
постепенно, а не сразу помногу.

## Безопасность

> **`SESSION_STRING` = полный доступ к твоему Telegram-аккаунту.** Любой, кто
> получит эту строку, сможет читать твою переписку, писать от твоего имени и
> сливать контакты. Это не «токен бота», это сессия твоего человеческого
> аккаунта.

Правила:

- Никогда не коммить `SESSION_STRING` в репозиторий.
- Никогда не пересылай её в чаты, не вставляй в issue/PR/комментарии.
- Храни только в Railway → Variables или в `.env` на сервере (с правами
  `chmod 600`) — и локально в `.env`, который покрыт `.gitignore`.
- Если случайно засветил — открой Telegram → Settings → Devices → **Terminate
  session** для этой сессии, и сразу перегенерируй через
  `python scripts/generate_session.py`.
- `API_ID` / `API_HASH` тоже считай секретами.

## Troubleshooting

**`SESSION_STRING невалиден или сессия отозвана`**
Скорее всего ты завершил сессию вручную из приложения Telegram, или сменил
пароль 2FA. Запусти `python scripts/generate_session.py` локально и обнови
переменную на Railway.

**`UserBannedInChannelError` / `ChatWriteForbiddenError` / `ChannelPrivateError`**
Тебя кикнули из группы / отозвали права писать / группа стала приватной без
тебя. Удали этот чат из `TARGET_GROUPS`. Остальные группы всё равно получают
пост — бот не падает на этой ошибке.

**`SlowModeWaitError ... > max ...`**
В группе включён slow mode на N секунд, и N больше `MAX_SLOW_MODE_WAIT`. Либо
увеличь `MAX_SLOW_MODE_WAIT`, либо смирись (этот пост пропустится — следующий
по расписанию пройдёт).

**`FloodWait слишком долгий`**
Telegram временно ограничил скорость отправки. Бот один раз подождёт и
повторит, дальше — пропустит. Это нормально, особенно если сервис только что
рестартанул и пытается отработать пропущенный слот.

**После рестарта (редеплой) пропустил время поста**
APScheduler настроен с `misfire_grace_time=300` (5 минут): если бот был
выключен <5 минут — пост уйдёт сразу после старта. Дольше — слот пропустится,
следующий отработает по расписанию.

**`Skip broadcast: В drafts-канале нет постов с активным хэштегом`**
В канале-источнике нет ни одного сообщения с `#active` (или другой
`ACTIVE_TAG`). Зайди в канал, добавь хэштег к нужным сообщениям —
следующая рассылка их подхватит. Бот не падает на этой ситуации.

**`Failed to load posts from drafts channel`**
Не смог прочитать канал-источник: чаще всего `DRAFTS_SOURCE` указан с опечаткой
или userbot потерял доступ к каналу (был исключён). Проверь значение
переменной и членство в канале.

## Тесты и линтер

```bash
pip install -r requirements-dev.txt
pytest          # тесты sender'а
ruff check .    # линтер
ruff format --check .
```

## Структура

```
.
├── .env.example
├── .gitignore
├── .python-version
├── Procfile
├── README.md
├── pyproject.toml
├── railway.json
├── requirements.txt
├── requirements-dev.txt
├── userbot.service      # systemd-юнит для деплоя на VPS
├── scripts/
│   └── generate_session.py
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── logger.py
│   ├── main.py
│   ├── posts.py        # читает посты из приватного TG-канала
│   ├── scheduler.py
│   └── sender.py
└── tests/
    ├── __init__.py
    ├── test_posts.py
    └── test_sender.py
```

## Что НЕ делает этот бот

- Не использует Bot API — только User API через Telethon.
- Не пишет ни в какие группы, кроме указанных в `TARGET_GROUPS`.
- Не хранит Telethon-сессию в файле — только `StringSession` из env, работает
  одинаково локально / на Railway / на VPS.
- Не пишет логи в файл — только stdout (Railway или journalctl/systemd
  собирают сами).
- Не имеет веб-морды / БД / Redis / Docker — для текущего объёма это лишнее.
