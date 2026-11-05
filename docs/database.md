# Схема и модели базы данных

Структура базы данных спроектирована с использованием стандартного механизма Django ORM. Проект содержит две прикладные предметные области: управление заявками (`tickets`) и учет оборудования (`instruments`), а также опирается на стандартную модель пользователей Django (`auth_user`).

---

## 1. Описание сущностей и полей

### Таблица: `auth_user` (Системная модель пользователя Django)
- `id` (IntegerField, Primary Key, Auto Increment) — уникальный идентификатор.
- `username` (CharField, 150) — логин пользователя.
- `password` (CharField, 128) — хеш пароля (PBKDF2/SHA256).
- `is_staff` (BooleanField) — флаг доступа к панели администратора.
- `is_superuser` (BooleanField) — флаг суперпользователя со всеми правами.

---

### Таблица: `tickets_ticket` (Заявки / Инциденты)
Основная сущность подсистемы тикетов, фиксирующая проблему сотрудника.
- `id` (BigAutoField, Primary Key) — уникальный номер тикета.
- `title` (CharField, max_length=255) — краткая тема обращения.
- `description` (TextField) — детальное описание возникшей проблемы.
- `status` (CharField, max_length=32, default='new') — текущий статус обработки (`new`, `in_progress`, `closed`).
- `created_at` (DateTimeField, auto_now_add=True) — дата и время фиксации заявки.
- `updated_at` (DateTimeField, auto_now=True) — дата и время последнего редактирования.

---

### Таблица: `instruments_instrument` (Оборудование и инвентарь)
Каталог доступного для выдачи инструментария.
- `id` (BigAutoField, Primary Key) — уникальный идентификатор единицы учета.
- `name` (CharField, max_length=200) — наименование инструмента/устройства.
- `inventory_number` (CharField, max_length=100, unique=True) — уникальный инвентарный/серийный номер.
- `status` (CharField, max_length=32, default='available') — статус инвентаря (`available`, `in_use`, `maintenance`).
- `description` (TextField, blank=True) — дополнительное техническое описание.

---

### Таблица: `instruments_instrumentrequest` (Запросы на получение инвентаря)
Связующая сущность, фиксирующая потребность пользователя в конкретном оборудовании.
- `id` (BigAutoField, Primary Key) — номер запроса.
- `instrument_id` (ForeignKey -> `instruments_instrument.id`, ON DELETE CASCADE/PROTECT) — запрошенное оборудование.
- `user_id` (ForeignKey -> `auth_user.id`, ON DELETE CASCADE) — сотрудник, запросивший инструмент.
- `status` (CharField, max_length=32, default='pending') — состояние запроса (`pending`, `approved`, `rejected`, `returned`).
- `created_at` (DateTimeField, auto_now_add=True) — дата создания запроса.

---

### Таблица: `instruments_instrumentrequestevent` (Журнал аудита событий по инвентарю)
Таблица истории изменений и перемещений инструмента.
- `id` (BigAutoField, Primary Key) — уникальный номер записи в журнале.
- `request_id` (ForeignKey -> `instruments_instrumentrequest.id`, ON DELETE CASCADE) — связанный запрос.
- `action` (CharField, max_length=64) — выполненное действие (создание, утверждение, отказ, возврат).
- `instrument_name_snapshot` (CharField, max_length=200) — снимок (копия) названия инструмента на момент совершения операции для сохранения целостности исторических данных при изменении или удалении самого инструмента.
- `timestamp` (DateTimeField, auto_now_add=True) — точное серверное время фиксации события.

---

## 2. ER-диаграмма связей (Entity-Relationship)

```text
+------------------------------------+
|             auth_user              |
+------------------------------------+
| PK | id                            |
|    | username                      |
|    | password                      |
+----+-------------------------------+
                 |
                 | 1
                 |
                 | N
                 v
+------------------------------------+
|   instruments_instrumentrequest    |
+------------------------------------+
| PK | id                            |
| FK | user_id                       |
| FK | instrument_id  ---------------+------+
|    | status                        |      |
|    | created_at                    |      |
+----+-------------------------------+      |
                 |                          |
                 | 1                        | N:1
                 |                          |
                 | N                        v
                 v           +------------------------------------+
+--------------------------+ |        instruments_instrument      |
| instruments_instrument-  | +------------------------------------+
| requestevent             | | PK | id                            |
+--------------------------+ |    | name                          |
| PK | id                  | | UQ | inventory_number              |
| FK | request_id          | |    | status                        |
|    | action              | |    | description                   |
|    | instrument_name_    | +----+-------------------------------+
|    |   snapshot          |
|    | timestamp           |
+----+---------------------+

+------------------------------------+
|          tickets_ticket            |
+------------------------------------+
| PK | id                            |
|    | title                         |
|    | description                   |
|    | status                        |
|    | created_at                    |
|    | updated_at                    |
+----+-------------------------------+