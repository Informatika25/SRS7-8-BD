# Руководство по развёртыванию веб-приложения на платформе Render

Настоящее руководство регламентирует процесс подготовки, конфигурации и публикации веб-приложения на облачной PaaS-платформе [Render](https://render.com/) в связке с управляемой СУБД PostgreSQL (в рамках бесплатного тарифа Free) в соответствии с требованиями ПЗ №8 и СРС №8.

---

## 1. Архитектура развёрнутого приложения

Развёртывание базируется на разделении ответственности между компонентами и изоляции хранения данных:

```
[Браузер пользователя]
         │
         ▼ (HTTPS)
[Render Web Service] ──► [Gunicorn (WSGI)] ──► [WhiteNoise (Статика)]
                                  │
                                  ▼
                           [Django / DRF]
                                  │
                                  ▼ (Internal Database URL)
                       [Render PostgreSQL DB]
```

| Компонент | Назначение в архитектуре |
| :--- | :--- |
| **Render Web Service** | Хостинг веб-приложения с автоматическим HTTPS-сертификатом и балансировкой |
| **Gunicorn** | Промышленный WSGI-сервер для запуска Django в среде Linux |
| **Django / DRF** | Серверная бизнес-логика, рендеринг представлений и обработка REST API |
| **Render PostgreSQL** | Полноценная реляционная СУБД для постоянного (persistent) хранения данных |
| **WhiteNoise** | Прямая отдача сжатых статических файлов (CSS Tabler, JS, медиа) без отдельного Nginx |
| **Переменные окружения** | Безопасная передача секретов, флагов и параметров сети без изменения кода |

---

## 2. Предварительная подготовка проекта

### 2.1. Файл зависимостей `requirements.txt`
Для запуска проекта в облачном Linux-окружении в корне репозитория должен быть зафиксирован актуальный список библиотек:
```text
Django>=5.0,<6.0
djangorestframework>=3.14.0
python-dotenv>=1.0.0
dj-database-url>=2.1.0
psycopg[binary]>=3.1.18
gunicorn>=21.2.0
whitenoise[brotli]>=6.6.0
```

### 2.2. Сценарий сборки `build.sh`
В корне проекта создайте исполняемый bash-скрипт сборки:
```bash
#!/usr/bin/env bash
# Прерывать выполнение при возникновении ошибки
set -e

# Обновление пакетного менеджера и установка зависимостей
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Сборка статических файлов в STATIC_ROOT для WhiteNoise
python manage.py collectstatic --noinput

# Применение миграций схемы данных в подключенной СУБД
python manage.py migrate
```

> **Важно**: убедитесь, что скрипт имеет права на исполнение в Git:
> ```bash
> git update-index --chmod=+x build.sh
> git commit -m "Add executable permission to build.sh"
> git push
> ```

### 2.3. Исключения в `.gitignore`
Убедитесь, что временные файлы и локальные секреты не попадают в систему контроля версий:
```gitignore
*.pyc
__pycache__/
.venv/
env/
.env
db.sqlite3
staticfiles/
```

---

## 3. Конфигурация `config/settings.py`

В файле настроек Django должны быть реализованы чтение переменных окружения и интеграция облачных компонентов:

```python
import os
from pathlib import Path
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# 1. Секретный ключ (обязателен к передаче через env)
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured("Критическая ошибка: переменная DJANGO_SECRET_KEY не задана.")

# 2. Режим отладки (в продакшне строго False)
DEBUG = os.environ.get("DJANGO_DEBUG", "False").lower() == "true"

# 3. Разрешенные хосты
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if host.strip()
]

# 4. Доверенные источники для защиты от CSRF (с обязательным указанием протокола)
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "http://127.0.0.1:8000").split(",")
    if origin.strip()
]

# 5. Обработка заголовка HTTPS от прокси Render
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# 6. Подключение WhiteNoise (строго после SecurityMiddleware)
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# 7. База данных: парсинг DATABASE_URL с откатом на SQLite при локальной разработке
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# 8. Раздача статики через WhiteNoise
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    }
}
```

---

## 4. Пошаговое развёртывание на Render

### Шаг 1. Создание облачной базы данных PostgreSQL
1. Войдите в личный кабинет [Render Dashboard](https://dashboard.render.com/).
2. В правом верхнем углу нажмите **New +** ➔ выберите **PostgreSQL**.
3. Заполните карточку создания СУБД:
   - **Name**: `pz8-django-db` (наглядное имя ресурса);
   - **Database**: `srs_db` (имя базы данных);
   - **User**: `srs_user` (служебный пользователь);
   - **Region**: `Frankfurt (EU Central)` или `Oregon (US West)` (выберите регион, который будет совпадать с регионом Web Service);
   - **PostgreSQL Version**: оставить значение по умолчанию;
   - **Instance Type**: **Free**.
4. Нажмите **Create Database** и дождитесь завершения процедуры инициализации.
5. В открывшемся разделе **General** убедитесь, что параметр **Status** перешёл в состояние `Available`.
6. Перейдите в блок **Connections**, найдите строку **Internal Database URL** и скопируйте её значение при помощи иконки копирования.

> **Правило безопасности**:
> Значение `Internal Database URL` содержит сгенерированный пароль СУБД. Его **запрещено** публиковать в репозиториях, коде, скриншотах или текстах отчетов. Оно передаётся исключительно через переменные окружения Render.

---

### Шаг 2. Создание и настройка Web Service
1. В панели управления Render нажмите **New +** ➔ выберите **Web Service**.
2. Выберите пункт подключения GitHub-репозитория и укажите репозиторий с проектом.
3. Заполните основные параметры развёртывания:
   - **Name**: `pz8-django-app` (уникальное имя веб-сервиса);
   - **Region**: **тот же регион**, в котором была создана PostgreSQL (критично для доступности внутренней сети);
   - **Branch**: `main`;
   - **Root Directory**: оставить пустым (утилита `manage.py` находится в корне);
   - **Runtime**: `Python 3`;
   - **Build Command**: `bash build.sh`;
   - **Start Command**: `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`;
   - **Instance Type**: **Free**.

---

### Шаг 3. Конфигурация переменных окружения (Environment Variables)
В настройках создаваемого сервиса откройте вкладку **Environment** и добавьте 5 ключевых переменных:

| Имя переменной (Key) | Значение (Value) | Назначение и требования безопасности |
| :--- | :--- | :--- |
| `DATABASE_URL` | *Скопированный Internal Database URL* | Адрес внутренней сети Render для подключения Django к созданному PostgreSQL-инстансу. Не вводить пароль вручную. |
| `DJANGO_SECRET_KEY` | *Случайная строка символов* | Ключ криптографической подписи сессий и CSRF. Воспользуйтесь кнопкой **Generate** в интерфейсе Render. |
| `DJANGO_DEBUG` | `False` | Отключение режима отладки. Предотвращает показ технической информации и системных путей при возникновении ошибок. |
| `DJANGO_ALLOWED_HOSTS` | `pz8-django-app.onrender.com` | Имя хоста вашего Web Service на Render (строго **без** префикса `https://` и слэшей). |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://pz8-django-app.onrender.com` | Полный URL сервиса с обязательным указанием схемы `https://` для прохождения валидации изменяющих запросов. |

---

### Шаг 4. Сборка и первый запуск сервиса
1. Нажмите кнопку **Create Web Service** (или **Save Changes**).
2. Render автоматически запустит процесс сборки. Перейдите во вкладку **Logs** и проконтролируйте этапы:
   - Успешная установка зависимостей из `requirements.txt`;
   - Сборка статических файлов утилитой `collectstatic` в директорию `staticfiles/`;
   - Накат миграций `python manage.py migrate` на облачную PostgreSQL;
   - Старт Gunicorn-сервера (`Listening at: http://0.0.0.0:10000`).
3. При успешном развёртывании статус сервиса перейдёт в `Live`, и станет доступен публичный URL-адрес формата `https://<ваше-приложение>.onrender.com`.

---

### Шаг 5. Инициализация учетной записи администратора
Так как облачная PostgreSQL создана с нуля и не содержит локальных пользователей:
1. В панели управления вашим Web Service перейдите во вкладку **Shell**.
2. Дождитесь подключения терминала к контейнеру и выполните:
   ```bash
   python manage.py createsuperuser
   ```
3. Задайте логин, e-mail и надёжный пароль для доступа к административной панели.

---

## 5. Изоляция сред: почему SQLite не переносится в PostgreSQL

> **Принцип постоянства данных**:
> - Файловая система контейнеров Web Service на бесплатных тарифах облачных платформ является **эфемерной (ephemeral)**. При каждом новом деплое или перезапуске контейнер пересоздаётся с нуля.
> - Если использовать локальную базу `db.sqlite3`, все созданные записи **будут безвозвратно удаляться** при перезапуске сервиса.
> - Подключение отдельного сервиса PostgreSQL через `DATABASE_URL` гарантирует **постоянное (persistent) хранение данных**: база данных живёт независимо от веб-сервера, а её данные сохраняются при перезапусках приложения.
> - Данные из локальной SQLite не переносятся автоматически — в облачной базе справочники и пользователи создаются заново.

---

## 6. Проверка работоспособности развёрнутого сервиса

После завершения публикации выполните обязательную контрольную серию тестов:

1. **Проверка эндпоинта здоровья**:
   - Перейдите по адресу: `https://<ваше-приложение>.onrender.com/healthz/`.
   - Ожидаемый результат: HTTP 200 OK, JSON-ответ: `{"status": "ok"}`.
2. **Проверка статики (WhiteNoise)**:
   - Откройте главную страницу веб-приложения.
   - Ожидаемый результат: интерфейс отображается с полным оформлением Tabler UI, в инструментах разработчика (Network) отсутствуют ошибки 404 по статическим файлам (`.css`, `.js`).
3. **Проверка аутентификации и сессий**:
   - Авторизуйтесь под учетной записью суперпользователя через страницу входа.
   - Ожидаемый результат: успешный вход, создание сессионной cookie `sessionid`.
4. **Проверка взаимодействия с API (GET и POST/PATCH)**:
   - В интерфейсе создайте новую заявку или запрос инвентаря.
   - Измените статус заявки.
   - В панели DevTools ➔ **Network** убедитесь, что запросы выполняются со статусами `201 Created` и `200 OK`, а заголовок `X-CSRFToken` передаётся корректно.
5. **Проверка постоянства данных после перезапуска**:
   - Зафиксируйте созданные записи в интерфейсе.
   - В панели Render Web Service нажмите **Manual Deploy** ➔ **Restart Service**.
   - Дождитесь перезапуска и обновите страницу сайта: данные должны остаться на месте, подтверждая корректную запись в PostgreSQL.

---

## 7. Диагностика типовых ошибок развёртывания

| Симптом ошибки | Вероятная причина | Способ диагностики и устранения |
| :--- | :--- | :--- |
| **HTTP 400 Bad Request / DisallowedHost** | Домен сервиса отсутствует в настройках безопасности | Проверьте переменную `DJANGO_ALLOWED_HOSTS`. Убедитесь, что там указан актуальный домен Render без префикса `https://` и пробелов. |
| **HTTP 403 Forbidden / CSRF verification failed** | Несовпадение источника запроса с доверенным доменом | Проверьте переменную `DJANGO_CSRF_TRUSTED_ORIGINS`. В ней обязательно должен присутствовать протокол `https://` (например, `https://pz8-django-app.onrender.com`). |
| **CSS/JS не загружаются (ошибки 404)** | Не выполнен сбор статических файлов | Убедитесь, что в `build.sh` присутствует команда `python manage.py collectstatic --noinput`, а в `MIDDLEWARE` подключен `WhiteNoiseMiddleware`. |
| **OperationalError: could not connect to server** | Ошибка подключения к базе данных PostgreSQL | Проверьте значение `DATABASE_URL`. Убедитесь, что использован **Internal Database URL**, а инстансы PostgreSQL и Web Service находятся в **одном регионе**. |
| **ProgrammingError: relation does not exist** | В базе отсутствуют необходимые таблицы | Не были выполнены миграции. Запустите `python manage.py migrate` через вкладку **Shell** сервиса или убедитесь в наличии этой команды в `build.sh`. |
| **Данные пропадают после перезапуска сервиса** | Приложение работает на временной SQLite-БД | Переменная `DATABASE_URL` не передана или не читается в `settings.py`, из-за чего сервис использует дефолтный файл `db.sqlite3`. |