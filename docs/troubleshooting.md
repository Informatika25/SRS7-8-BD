# Типичные ошибки и руководство по диагностике

В данном руководстве собраны типовые неисправности, возникающие на этапах локального запуска, сборки и облачной эксплуатации веб-приложения на Render.

---

## 1. Сбой отправки форм и AJAX-запросов: «403 Forbidden (CSRF verification failed)»

- **Симптомы**:
  - При отправке POST-запроса на создание тикета или PATCH-запроса на смену статуса операция отклоняется с кодом `403 Forbidden`.
  - В ответе сервера возвращается HTML-страница или JSON с сообщением `CSRF verification failed. Request aborted` либо `Origin checking failed`.
- **Причина**:
  - На облачном сервере в `settings.py` не настроен список доверенных источников `CSRF_TRUSTED_ORIGINS`, либо заголовок `Origin`/`Referer` не совпадает с публичным HTTPS-доменом.
  - В клиентском JavaScript (`app.js`) в заголовках асинхронного `fetch`-запроса не передан заголовок `X-CSRFToken`, либо токен не извлечён из cookie `csrftoken`.
- **Диагностика**:
  1. Откройте инструменты разработчика браузера (F12) -> вкладка **Network**.
  2. Выберите неуспешный запрос (`POST /api/tickets/` или `PATCH /api/tickets/<id>/`) и изучите вкладку **Headers**:
     - Проверьте наличие заголовка запроса `X-CSRFToken`.
     - Проверьте значение `Origin` (должно быть `https://<ваш-сервис>.onrender.com`).
  3. В логах сервиса на Render найдите строку: `Forbidden (Origin checking failed - https://... does not match any trusted origins)`.
- **Устранение**:
  1. В панели Render в разделе **Environment** проверьте переменную `DJANGO_CSRF_TRUSTED_ORIGINS`. Значение обязательно должно содержать схему протокола `https://`:
     ```text
     DJANGO_CSRF_TRUSTED_ORIGINS=[https://pz8-django-app.onrender.com](https://pz8-django-app.onrender.com)
     ```
  2. Убедитесь, что в `tickets/static/tickets/app.js` перед отправкой запроса извлекается cookie и прикрепляется к заголовкам:
     ```javascript
     function getCookie(name) {
       let cookieValue = null;
       if (document.cookie && document.cookie !== '') {
         const cookies = document.cookie.split(';');
         for (let i = 0; i < cookies.length; i++) {
           const cookie = cookies[i].trim();
           if (cookie.substring(0, name.length + 1) === (name + '=')) {
             cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
             break;
           }
         }
       }
       return cookieValue;
     }

     // При вызове fetch:
     fetch(url, {
       method: 'PATCH',
       headers: {
         'Content-Type': 'application/json',
         'X-CSRFToken': getCookie('csrftoken')
       },
       body: JSON.stringify(payload)
     });
     ```

---

## 2. Нарушение стилизации интерфейса: файлы CSS/JS не загружаются (ошибки 404)

- **Симптомы**:
  - Страницы открываются в виде сырого неформатированного HTML-текста без стилей Tabler.
  - Консоль браузера сообщает об ошибках загрузки ресурсов: `GET https://.../static/tabler/tabler.min.css net::ERR_ABORTED 404 (Not Found)`.
- **Причина**:
  - На этапе сборки не была выполнена команда сбора статики `collectstatic`, каталог `staticfiles` пуст.
  - В `config/settings.py` отсутствует или некорректно расположен middleware библиотеки `WhiteNoise`.
  - В режиме `DEBUG = False` встроенный сервер разработки Django отключает автоматическую раздачу статики, а WhiteNoise не настроен.
- **Диагностика**:
  1. Во вкладке **Network** убедитесь, что именно запросы по путям `/static/...` возвращают статус `404 Not Found`.
  2. Изучите лог сборки (Build Logs) на Render: присутствует ли строка `... static files copied to '/opt/render/project/src/staticfiles'`.
- **Устранение**:
  1. В `config/settings.py` проверьте порядок подключения в списке `MIDDLEWARE` (`WhiteNoiseMiddleware` обязан следовать строго сразу после `SecurityMiddleware`):
     ```python
     MIDDLEWARE = [
         "django.middleware.security.SecurityMiddleware",
         "whitenoise.middleware.WhiteNoiseMiddleware",
         "django.contrib.sessions.middleware.SessionMiddleware",
         # ...
     ]
     ```
  2. Проверьте настройки статики в `config/settings.py`:
     ```python
     STATIC_URL = "static/"
     STATIC_ROOT = BASE_DIR / "staticfiles"
     STORAGES = {
         "staticfiles": {
             "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
         },
     }
     ```
  3. Убедитесь, что в `build.sh` включена команда сборки:
     ```bash
     python manage.py collectstatic --noinput
     ```

---

## 3. Блокировка доступа хоста: «DisallowedHost at /» (HTTP 400 Bad Request)

- **Симптомы**:
  - При попытке открыть публичный адрес `https://<сервис>.onrender.com` браузер отображает ошибку `Bad Request (400)`.
  - При `DEBUG = True` отображается страница с заголовком: `DisallowedHost at /: Invalid HTTP_HOST header: 'pz8-django-app.onrender.com'. You may need to add 'pz8-django-app.onrender.com' to ALLOWED_HOSTS`.
- **Причина**:
  - Доменное имя сервера, назначенное платформой Render, не внесено в список разрешённых узлов `ALLOWED_HOSTS`.
- **Диагностика**:
  - В логах сервиса на Render (Logs) фиксируется запись уровня ERROR: `django.security.DisallowedHost: Invalid HTTP_HOST header: 'pz8-django-app.onrender.com'`.
- **Устранение**:
  1. Откройте настройки Web Service на Render -> раздел **Environment**.
  2. В переменную `DJANGO_ALLOWED_HOSTS` передайте точный домен **без указания протокола и слэшей**:
     ```text
     DJANGO_ALLOWED_HOSTS=pz8-django-app.onrender.com,127.0.0.1,localhost
     ```
  3. Сохраните изменения: Render автоматически перезапустит контейнер с обновлённой конфигурацией.

---

## 4. Ошибка структуры БД: «ProgrammingError: relation "..." does not exist»

- **Симптомы**:
  - При открытии любой страницы приложения или обращении к API сервер возвращает внутреннюю ошибку `500 Internal Server Error`.
  - В логах отображается исключение: `django.db.utils.ProgrammingError: relation "tickets_ticket" does not exist` (или аналогичное для моделей `instruments`).
- **Причина**:
  - Подключение к PostgreSQL прошло успешно, но к базе данных не были применены файлы миграций Django. Таблицы в схеме данных не созданы.
- **Диагностика**:
  - В серверных логах Render найдите трассировку ошибки (Traceback), заканчивающуюся строкой `psycopg2.errors.UndefinedTable: relation "..." does not exist`.
- **Устранение**:
  1. В панели управления Render перейдите в раздел **Shell** вашего Web Service.
  2. Выполните накат миграций вручную:
     ```bash
     python manage.py migrate
     ```
  3. Проверьте статус применения миграций:
     ```bash
     python manage.py showmigrations
     ```
     Все миграции приложений `tickets`, `instruments`, `auth` и `admin` должны быть отмечены символом `[X]`.

---

## 5. Ошибка соединения с СУБД: «OperationalError: could not connect to server»

- **Симптомы**:
  - Веб-сервис аварийно завершает работу при старте (`Application failed to start`).
  - Команда `manage.py check` или попытка обработки запроса завершается ошибкой: `psycopg2.OperationalError: could not connect to server: Connection refused`.
- **Причина**:
  - Переменная `DATABASE_URL` не задана или содержит некорректные данные.
  - Использован публичный адрес (External Database URL) вместо внутреннего (Internal Database URL), либо инстанс PostgreSQL остановлен / находится в процессе создания (статус отличается от `Available`).
  - База данных и Web Service созданы в разных регионах Render (внутренний адрес недоступен межрегионально).
- **Диагностика**:
  - Изучите логи сервиса на этапе развёртывания. Наличие сообщений `Name or service not known` или `Connection timed out` свидетельствует о недоступности сетевого адреса СУБД.
- **Устранение**:
  1. Перейдите на страницу инстанса PostgreSQL в Render и убедитесь, что статус равен **Available**.
  2. Проверьте регион (Region) обоих сервисов: они должны совпадать (например, оба `Frankfurt`).
  3. В разделе **Connections** базы данных заново скопируйте **Internal Database URL**.
  4. В настройках Web Service (**Environment**) обновите значение переменной `DATABASE_URL` (без лишних пробелов и кавычек).

---

## 6. Исчезновение данных после перезапуска сервиса

- **Симптомы**:
  - Пользователь регистрируется, создаёт тикеты и заявки на инвентарь — всё работает корректно.
  - После перезапуска сервиса (кнопка Restart в Render, автоматический деплой или простой бесплатного контейнера) все созданные данные исчезают, а созданный суперпользователь не может войти в систему.
- **Причина**:
  - Приложение продолжает использовать локальную базу данных SQLite (`db.sqlite3`), размещённую на эфемерном (временном) диске контейнера Render. При каждом перезапуске контейнера файловая система сбрасывается к исходному состоянию из Git-репозитория.
  - Это происходит, если в `settings.py` парсинг `DATABASE_URL` не срабатывает и отрабатывает дефолтное значение `sqlite:///db.sqlite3`, либо переменная `DATABASE_URL` не была добавлена в Environment.
- **Диагностика**:
  1. В панели Render откройте вкладку **Shell** и проверьте текущую строку подключения:
     ```bash
     python manage.py shell -c "from django.conf import settings; print(settings.DATABASES['default']['ENGINE'])"
     ```
  2. Если вывод равен `django.db.backends.sqlite3` вместо `django.db.backends.postgresql`, сервис работает мимо PostgreSQL.
- **Устранение**:
  1. Убедитесь, что в `config/settings.py` используется библиотека `dj-database-url`:
     ```python
     import dj_database_url
     DATABASES = {
         "default": dj_database_url.config(
             default="sqlite:///db.sqlite3",
             conn_max_age=600,
             conn_health_checks=True,
         )
     }
     ```
  2. Проверьте вкладку **Environment** на Render и убедитесь, что параметр `DATABASE_URL` присутствует и начинается с `postgresql://`.

---

## 7. Ошибка прав доступа при сборке: «bash: ./build.sh: Permission denied»

- **Симптомы**:
  - На этапе сборки (Build Step) в логах Render появляется ошибка:
    ```text
    ==> Running build command 'bash build.sh'...
    bash: ./build.sh: Permission denied
    ==> Build failed 
    ```
- **Причина**:
  - Файл `build.sh` был создан в операционной системе Windows или закоммичен в репозиторий Git без POSIX-бита исполняемости (`+x`).
- **Диагностика**:
  - В терминале выполните проверку прав: `git ls-files --stage build.sh`. Если режим равен `100644` вместо `100755`, файл не является исполняемым для Git.
- **Устранение**:
  1. В локальном репозитории выполните команду назначения флага исполняемости через индекс Git:
     ```bash
     git update-index --chmod=+x build.sh
     git commit -m "Fix execution permissions for build.sh"
     git push
     ```
  2. Либо в настройках Web Service на Render временно укажите команду сборки в виде прямого вызова интерпретатора:
     ```text
     bash build.sh
     ```