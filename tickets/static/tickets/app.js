const csrfToken = document.querySelector(
    "[name=csrfmiddlewaretoken]"
).value;

const currentUserId = Number(document.body.dataset.userId);
const isStaff = document.body.dataset.isStaff === "true";

// Элементы страницы
const instrumentSelect = document.getElementById("instrument");
const requestForm = document.getElementById("instrument-request-form");
const quantityInput = document.getElementById("quantity");

const instrumentsList = document.getElementById("instruments-list");
const requestsList = document.getElementById("requests-list");
const historyList = document.getElementById("history-list");

const statusFilter = document.getElementById("status-filter");
const categoryFilter = document.getElementById("category-filter");

const message = document.getElementById("message");
const loading = document.getElementById("loading");

// Названия статусов
const statusLabels = {
    new: "Новая",
    approved: "Одобрена",
    rejected: "Отклонена",
    returned: "Возвращена"
};

const statusClasses = {
    new: "bg-blue-lt",
    approved: "bg-green-lt",
    rejected: "bg-red-lt",
    returned: "bg-secondary-lt"
};

// Отправка запросов к API
async function apiRequest(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
            ...(options.headers || {})
        },
        credentials: "same-origin"
    });

    let data = null;

    if (response.status !== 204) {
        data = await response.json().catch(() => null);
    }

    if (!response.ok) {
        let errorMessage = data?.detail;

        if (!errorMessage && data) {
            if (Array.isArray(data)) {
                errorMessage = data.join(" ");
            } else if (typeof data === "object") {
                errorMessage = Object.entries(data)
                    .map(([field, errors]) => {
                        const text = Array.isArray(errors)
                            ? errors.join(" ")
                            : String(errors);

                        return `${field}: ${text}`;
                    })
                    .join(" ");
            }
        }

        throw new Error(
            errorMessage || `Ошибка сервера: ${response.status}`
        );
    }

    return data;
}

// Сообщения пользователю
let messageTimeout;

function hideMessage() {
    clearTimeout(messageTimeout);
    message.style.display = "none";
}

function showMessage(text, isError = false) {
    clearTimeout(messageTimeout);

    message.textContent = text;

    message.className = isError
        ? "alert alert-danger shadow"
        : "alert alert-success shadow";

    // Закрепляем уведомление в правом нижнем углу
    message.style.position = "fixed";
    message.style.bottom = "20px";
    message.style.right = "20px";
    message.style.top = "auto";
    message.style.left = "auto";
    message.style.zIndex = "99999";
    message.style.maxWidth = "400px";
    message.style.display = "block";

    messageTimeout = setTimeout(() => {
        hideMessage();
    }, 4000);
}

// Создание HTML-элемента
function createElement(tag, className, text = "") {
    const element = document.createElement(tag);

    if (className) {
        element.className = className;
    }

    element.textContent = text;

    return element;
}

// Получение списка категорий
async function loadCategories() {
    const categories = await apiRequest(
        "/api/instrument-categories/"
    );

    categoryFilter.replaceChildren();

    const allOption = createElement(
        "option",
        "",
        "Все категории"
    );

    allOption.value = "";
    categoryFilter.append(allOption);

    for (const category of categories) {
        const option = createElement(
            "option",
            "",
            category.name
        );

        option.value = category.id;

        categoryFilter.append(option);
    }
}

// Получение инструментов
async function loadInstruments() {
    const instruments = await apiRequest(
        "/api/instruments/"
    );

    instrumentsList.replaceChildren();
    instrumentSelect.replaceChildren();

    const placeholder = createElement(
        "option",
        "",
        "Выберите инструмент"
    );

    placeholder.value = "";
    instrumentSelect.append(placeholder);

    let availableTotal = 0;

    for (const instrument of instruments) {
        availableTotal += instrument.available_quantity;

        // Карточка инструмента
        const column = createElement(
            "div",
            "col-sm-6 col-lg-3"
        );

        const card = createElement(
            "div",
            "card h-100"
        );

        const body = createElement(
            "div",
            "card-body"
        );

        const name = createElement(
            "h3",
            "card-title",
            instrument.name
        );

        const category = createElement(
            "p",
            "text-secondary mb-2",
            instrument.category_name
        );

        const description = createElement(
            "p",
            "text-secondary small",
            instrument.description || "Описание отсутствует."
        );

        const quantity = createElement(
            "div",
            "mt-3 fw-bold",
            `Доступно: ${instrument.available_quantity} из ${instrument.total_quantity}`
        );

        body.append(
            name,
            category,
            description,
            quantity
        );

        card.append(body);
        column.append(card);
        instrumentsList.append(column);

        // Вариант для формы заявки
        const option = createElement(
            "option",
            "",
            `${instrument.name} — доступно: ${instrument.available_quantity}`
        );

        option.value = instrument.id;
        option.disabled = instrument.available_quantity === 0;

        instrumentSelect.append(option);
    }

    document.getElementById(
        "total-instruments"
    ).textContent = instruments.length;

    document.getElementById(
        "available-instruments"
    ).textContent = availableTotal;
}

// Создание заявки
requestForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const instrumentId = Number(instrumentSelect.value);
    const quantity = Number(quantityInput.value);

    if (!instrumentId || quantity <= 0) {
        showMessage(
            "Выберите инструмент и укажите количество больше нуля.",
            true
        );
        return;
    }

    try {
        await apiRequest("/api/instrument-requests/", {
            method: "POST",
            body: JSON.stringify({
                instrument: instrumentId,
                quantity: quantity
            })
        });

        requestForm.reset();

        showMessage("Заявка успешно создана.");

        await refreshPage();

    } catch (error) {
        showMessage(
            "Не удалось создать заявку: " + error.message,
            true
        );
    }
});

// Получение заявок с учётом фильтров
async function loadRequests() {
    loading.hidden = false;

    const params = new URLSearchParams();

    if (statusFilter.value) {
        params.set("status", statusFilter.value);
    }

    if (categoryFilter.value) {
        params.set("category", categoryFilter.value);
    }

    const query = params.toString();

    const url = "/api/instrument-requests/" +
        (query ? "?" + query : "");

    try {
        const requests = await apiRequest(url);

        renderRequests(requests);

        document.getElementById(
            "total-requests"
        ).textContent = requests.length;

    } catch (error) {
        showMessage(
            "Не удалось загрузить заявки: " + error.message,
            true
        );
    } finally {
        loading.hidden = true;
    }
}

// Отображение списка заявок
function renderRequests(requests) {
    requestsList.replaceChildren();

    if (!requests.length) {
        requestsList.append(
            createElement(
                "p",
                "text-secondary py-3",
                "Заявки не найдены."
            )
        );

        return;
    }

    for (const request of requests) {
        const row = createElement(
            "div",
            "border-bottom py-3"
        );

        const top = createElement(
            "div",
            "d-flex justify-content-between align-items-start gap-3 flex-wrap"
        );

        const info = createElement("div", "");

        const title = createElement(
            "h3",
            "mb-1",
            `Заявка №${request.id} — ${request.instrument_name}`
        );

        const details = createElement(
            "p",
            "text-secondary small mb-1",
            `Количество: ${request.quantity}`
        );

        const owner = createElement(
            "p",
            "text-secondary small mb-1",
            `Пользователь: ${request.owner_name}`
        );

        const date = createElement(
            "p",
            "text-secondary small mb-0",
            `Создана: ${new Date(request.created_at).toLocaleString("ru-RU")}`
        );

        info.append(title, details, owner, date);

        const actions = createElement(
            "div",
            "d-flex align-items-center gap-2 flex-wrap"
        );

        const status = createElement(
            "span",
            `badge ${statusClasses[request.status] || "bg-secondary-lt"}`,
            statusLabels[request.status] || request.status
        );

        actions.append(status);

        // Кнопки сотрудника
        if (isStaff) {
            if (request.status === "new") {
                const approveButton = createElement(
                    "button",
                    "btn btn-success btn-sm",
                    "Одобрить"
                );

                approveButton.type = "button";

                approveButton.addEventListener("click", () => {
                    processRequest(
                        request.id,
                        "approve"
                    );
                });

                const rejectButton = createElement(
                    "button",
                    "btn btn-outline-danger btn-sm",
                    "Отклонить"
                );

                rejectButton.type = "button";

                rejectButton.addEventListener("click", () => {
                    rejectRequest(request.id);
                });

                actions.append(
                    approveButton,
                    rejectButton
                );
            }

            if (request.status === "approved") {
                const returnButton = createElement(
                    "button",
                    "btn btn-primary btn-sm",
                    "Оформить возврат"
                );

                returnButton.type = "button";

                returnButton.addEventListener("click", () => {
                    processRequest(
                        request.id,
                        "return_instrument"
                    );
                });

                actions.append(returnButton);
            }
        }

        // Редактирование и удаление собственной новой заявки
        if (
            request.owner === currentUserId &&
            request.status === "new"
        ) {
            const editButton = createElement(
                "button",
                "btn btn-outline-primary btn-sm",
                "Изменить"
            );

            editButton.type = "button";

            editButton.addEventListener("click", () => {
                editRequest(request);
            });

            const deleteButton = createElement(
                "button",
                "btn btn-outline-danger btn-sm",
                "Удалить"
            );

            deleteButton.type = "button";

            deleteButton.addEventListener("click", () => {
                deleteRequest(request.id);
            });

            actions.append(editButton, deleteButton);
        }

        const historyButton = createElement(
            "button",
            "btn btn-outline-secondary btn-sm",
            "История"
        );

        historyButton.type = "button";

        historyButton.addEventListener("click", () => {
            loadHistory(request.id);
        });

        actions.append(historyButton);

        top.append(info, actions);
        row.append(top);

        requestsList.append(row);
    }
}

// Одобрение или возврат
async function processRequest(requestId, action) {
    const messages = {
        approve: "Вы уверены, что хотите одобрить заявку?",
        return_instrument: "Подтвердить возврат инструментов?"
    };

    if (!confirm(messages[action])) {
        return;
    }

    try {
        await apiRequest(
            `/api/instrument-requests/${requestId}/${action}/`,
            { method: "POST" }
        );

        showMessage("Действие успешно выполнено.");

        await refreshPage();

    } catch (error) {
        showMessage(
            "Не удалось выполнить действие: " + error.message,
            true
        );
    }
}

// Отклонение заявки
async function rejectRequest(requestId) {
    const reason = prompt(
        "Укажите причину отказа:"
    );

    if (reason === null) {
        return;
    }

    if (!reason.trim()) {
        showMessage(
            "Необходимо указать причину отказа.",
            true
        );
        return;
    }

    try {
        await apiRequest(
            `/api/instrument-requests/${requestId}/reject/`,
            {
                method: "POST",
                body: JSON.stringify({
                    reason: reason.trim()
                })
            }
        );

        showMessage("Заявка отклонена.");

        await refreshPage();

    } catch (error) {
        showMessage(
            "Не удалось отклонить заявку: " + error.message,
            true
        );
    }
}

// Изменение собственной заявки
async function editRequest(request) {
    const newQuantity = prompt(
        "Введите новое количество:",
        request.quantity
    );

    if (newQuantity === null) {
        return;
    }

    const quantity = Number(newQuantity);

    if (!Number.isInteger(quantity) || quantity <= 0) {
        showMessage(
            "Количество должно быть целым числом больше нуля.",
            true
        );
        return;
    }

    try {
        await apiRequest(
            `/api/instrument-requests/${request.id}/`,
            {
                method: "PATCH",
                body: JSON.stringify({
                    quantity: quantity
                })
            }
        );

        showMessage("Заявка успешно изменена.");

        await refreshPage();

    } catch (error) {
        showMessage(
            "Не удалось изменить заявку: " + error.message,
            true
        );
    }
}

// Удаление заявки
async function deleteRequest(requestId) {
    if (!confirm("Вы действительно хотите удалить эту заявку?")) {
        return;
    }

    try {
        await apiRequest(
            `/api/instrument-requests/${requestId}/`,
            { method: "DELETE" }
        );

        showMessage("Заявка успешно удалена.");

        historyList.textContent =
            "Выберите заявку, чтобы посмотреть её историю.";

        await refreshPage();

    } catch (error) {
        showMessage(
            "Не удалось удалить заявку: " + error.message,
            true
        );
    }
}

// История событий
async function loadHistory(requestId) {
    try {
        const events = await apiRequest(
            `/api/instrument-requests/${requestId}/history/`
        );

        historyList.replaceChildren();

        const heading = createElement(
            "h3",
            "mb-3",
            `История заявки №${requestId}`
        );

        historyList.append(heading);

        if (!events.length) {
            historyList.append(
                createElement(
                    "p",
                    "text-secondary",
                    "Событий пока нет."
                )
            );
            return;
        }

        for (const event of events) {
            const item = createElement(
                "div",
                "border-bottom py-2"
            );

            const action = createElement(
                "div",
                "fw-bold",
                event.action_display
            );

            const initiator = createElement(
                "div",
                "text-secondary small",
                `Инициатор: ${event.initiator_name || "Не указан"}`
            );

            const date = createElement(
                "div",
                "text-secondary small",
                new Date(event.created_at).toLocaleString("ru-RU")
            );

            const comment = createElement(
                "p",
                "mb-0 mt-1",
                event.comment || ""
            );

            item.append(action, initiator, date, comment);
            historyList.append(item);
        }

    } catch (error) {
        showMessage(
            "Не удалось загрузить историю: " + error.message,
            true
        );
    }
}

// Обновление данных после действий
async function refreshPage() {
    await loadInstruments();
    await loadRequests();
}

// Фильтры
statusFilter.addEventListener(
    "change",
    loadRequests
);

categoryFilter.addEventListener(
    "change",
    loadRequests
);

// Запуск страницы
async function initialize() {
    try {
        await loadCategories();
        await refreshPage();

    } catch (error) {
        showMessage(
            "Ошибка загрузки страницы: " + error.message,
            true
        );
    }
}

initialize();
