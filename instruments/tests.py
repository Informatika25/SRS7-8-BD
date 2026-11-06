from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from instruments.models import (
    InstrumentCategory,
    Instrument,
    InstrumentRequest,
    InstrumentRequestEvent,
)

User = get_user_model()

REQUESTS_URL = "/api/instrument-requests/"


class BaseInstrumentTestCase(APITestCase):

    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff_user",
            password="test12345",
            is_staff=True,
        )
        self.owner = User.objects.create_user(
            username="owner_user",
            password="test12345",
        )
        self.other_user = User.objects.create_user(
            username="other_user",
            password="test12345",
        )

        self.category = InstrumentCategory.objects.create(name="Гитары")
        self.category2 = InstrumentCategory.objects.create(name="Клавишные")

        self.instrument = Instrument.objects.create(
            name="Акустическая гитара",
            category=self.category,
            total_quantity=5,
            available_quantity=5,
        )
        self.instrument2 = Instrument.objects.create(
            name="Синтезатор",
            category=self.category2,
            total_quantity=3,
            available_quantity=3,
        )

        self.client = APIClient()

    def login(self, user):
        self.client.force_authenticate(user=user)

    def create_request(self, owner=None, instrument=None,
                       quantity=2, req_status="new"):
        """Создаёт заявку напрямую через ORM (в обход API)."""
        return InstrumentRequest.objects.create(
            instrument=instrument or self.instrument,
            owner=owner or self.owner,
            quantity=quantity,
            status=req_status,
        )


class CreateRequestTests(BaseInstrumentTestCase):
    # Проверка №1. Создание заявки
    def test_create_request_creates_event(self):
        self.login(self.owner)

        response = self.client.post(
            REQUESTS_URL,
            {"instrument": self.instrument.id, "quantity": 2},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        request_id = response.data["id"]
        self.assertTrue(
            InstrumentRequest.objects.filter(
                id=request_id, owner=self.owner, status="new"
            ).exists()
        )
        self.assertTrue(
            InstrumentRequestEvent.objects.filter(
                request_id=request_id, action="created"
            ).exists()
        )

    def test_create_request_more_than_available(self):
        self.login(self.owner)

        response = self.client.post(
            REQUESTS_URL,
            {"instrument": self.instrument.id, "quantity": 10},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("quantity", response.data)
        self.assertEqual(InstrumentRequest.objects.count(), 0)


class ApproveRequestTests(BaseInstrumentTestCase):
    # Проверка №2. Одобрение заявки
    def test_approve_changes_stock_status_and_history(self):
        request = self.create_request(quantity=2)
        self.login(self.staff)

        response = self.client.post(f"{REQUESTS_URL}{request.id}/approve/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.instrument.refresh_from_db()
        request.refresh_from_db()

        self.assertEqual(self.instrument.available_quantity, 3)
        self.assertEqual(request.status, "approved")
        self.assertEqual(request.processed_by, self.staff)
        self.assertTrue(
            InstrumentRequestEvent.objects.filter(
                request=request, action="approved"
            ).exists()
        )

    # Проверка №3. Запрещённый переход (повторное одобрение)
    def test_repeated_approve_is_rejected(self):
        request = self.create_request(quantity=2)
        self.login(self.staff)

        self.client.post(f"{REQUESTS_URL}{request.id}/approve/")
        events_after_first = InstrumentRequestEvent.objects.filter(
            request=request
        ).count()

        response = self.client.post(f"{REQUESTS_URL}{request.id}/approve/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.instrument.refresh_from_db()
        self.assertEqual(self.instrument.available_quantity, 3)
        self.assertEqual(
            InstrumentRequestEvent.objects.filter(request=request).count(),
            events_after_first,
        )

    # Проверка №4. Обычный пользователь не может одобрять
    def test_regular_user_cannot_approve(self):
        request = self.create_request(quantity=2)
        self.login(self.owner)

        response = self.client.post(f"{REQUESTS_URL}{request.id}/approve/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.instrument.refresh_from_db()
        request.refresh_from_db()
        self.assertEqual(self.instrument.available_quantity, 5)
        self.assertEqual(request.status, "new")


class RejectRequestTests(BaseInstrumentTestCase):
    # Проверка №5. Отклонение заявки
    def test_reject_without_reason(self):
        request = self.create_request()
        self.login(self.staff)

        response = self.client.post(
            f"{REQUESTS_URL}{request.id}/reject/",
            {"reason": "   "},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        request.refresh_from_db()
        self.assertEqual(request.status, "new")

    def test_reject_with_reason(self):
        request = self.create_request()
        self.login(self.staff)

        response = self.client.post(
            f"{REQUESTS_URL}{request.id}/reject/",
            {"reason": "Нет документов"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        request.refresh_from_db()
        self.assertEqual(request.status, "rejected")
        self.assertEqual(request.rejection_reason, "Нет документов")
        self.assertTrue(
            InstrumentRequestEvent.objects.filter(
                request=request, action="rejected"
            ).exists()
        )


class ReturnRequestTests(BaseInstrumentTestCase):
    def test_return_restores_stock(self):
        request = self.create_request(quantity=2)
        self.login(self.staff)

        self.client.post(f"{REQUESTS_URL}{request.id}/approve/")
        response = self.client.post(
            f"{REQUESTS_URL}{request.id}/return_instrument/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.instrument.refresh_from_db()
        request.refresh_from_db()
        self.assertEqual(self.instrument.available_quantity, 5)
        self.assertEqual(request.status, "returned")

    def test_return_of_new_request_is_rejected(self):
        request = self.create_request(quantity=2)
        self.login(self.staff)

        response = self.client.post(
            f"{REQUESTS_URL}{request.id}/return_instrument/"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.instrument.refresh_from_db()
        self.assertEqual(self.instrument.available_quantity, 5)


class AccessAndEditTests(BaseInstrumentTestCase):
    # Проверка №6. Права доступа, изменение и удаление заявок
    def test_other_user_cannot_see_foreign_request(self):
        request = self.create_request(owner=self.owner)
        self.login(self.other_user)

        response = self.client.get(f"{REQUESTS_URL}{request.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_other_user_list_does_not_contain_foreign_requests(self):
        self.create_request(owner=self.owner)
        self.login(self.other_user)

        response = self.client.get(REQUESTS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_other_user_cannot_delete_foreign_request(self):
        request = self.create_request(owner=self.owner)
        self.login(self.other_user)

        response = self.client.delete(f"{REQUESTS_URL}{request.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(
            InstrumentRequest.objects.filter(id=request.id).exists()
        )

    # Проверка №7. Прямая смена статуса через PATCH
    def test_patch_status_directly_is_rejected(self):
        request = self.create_request()
        self.login(self.owner)

        response = self.client.patch(
            f"{REQUESTS_URL}{request.id}/",
            {"status": "approved"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        request.refresh_from_db()
        self.assertEqual(request.status, "new")

    def test_owner_can_edit_quantity_of_new_request(self):
        request = self.create_request(quantity=2)
        self.login(self.owner)

        response = self.client.patch(
            f"{REQUESTS_URL}{request.id}/",
            {"quantity": 3},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        request.refresh_from_db()
        self.assertEqual(request.quantity, 3)

    def test_cannot_delete_approved_request(self):
        request = self.create_request(
            owner=self.owner, req_status="approved"
        )
        self.login(self.owner)

        response = self.client.delete(f"{REQUESTS_URL}{request.id}/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(
            InstrumentRequest.objects.filter(id=request.id).exists()
        )

    def test_owner_can_delete_new_request(self):
        request = self.create_request(owner=self.owner)
        self.login(self.owner)

        response = self.client.delete(f"{REQUESTS_URL}{request.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            InstrumentRequest.objects.filter(id=request.id).exists()
        )


class FilterTests(BaseInstrumentTestCase):
    # Проверка №8. Серверные фильтры по статусу и категории
    def setUp(self):
        super().setUp()
        self.r_new_guitar = self.create_request(
            instrument=self.instrument, req_status="new"
        )
        self.r_approved_guitar = self.create_request(
            instrument=self.instrument, req_status="approved"
        )
        self.r_new_synth = self.create_request(
            instrument=self.instrument2, req_status="new"
        )
        self.login(self.owner)

    def get_ids(self, query):
        response = self.client.get(f"{REQUESTS_URL}?{query}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return {item["id"] for item in response.data}

    def test_filter_by_status(self):
        ids = self.get_ids("status=new")
        self.assertEqual(
            ids, {self.r_new_guitar.id, self.r_new_synth.id}
        )

    def test_filter_by_category(self):
        ids = self.get_ids(f"category={self.category.id}")
        self.assertEqual(
            ids, {self.r_new_guitar.id, self.r_approved_guitar.id}
        )

    def test_filter_by_status_and_category(self):
        ids = self.get_ids(f"status=new&category={self.category.id}")
        self.assertEqual(ids, {self.r_new_guitar.id})


class TransactionRollbackTest(APITestCase):
    # Проверка №9. Откат составной операции при сбое

    def test_approve_rollback_when_history_creation_fails(self):
        User = get_user_model()

        staff = User.objects.create_user(
            username="staff_test",
            password="test12345",
            is_staff=True,
        )
        owner = User.objects.create_user(
            username="owner_test",
            password="test12345",
        )
        category = InstrumentCategory.objects.create(
            name="Тестовая категория"
        )
        instrument = Instrument.objects.create(
            name="Тестовая гитара",
            description="Тестовый инструмент",
            category=category,
            total_quantity=5,
            available_quantity=5,
        )
        request = InstrumentRequest.objects.create(
            instrument=instrument,
            owner=owner,
            quantity=2,
            status="new",
        )
        InstrumentRequestEvent.objects.create(
            request=request,
            initiator=owner,
            action="created",
            comment="Заявка создана",
        )
        events_before = InstrumentRequestEvent.objects.filter(
            request=request
        ).count()

        client = APIClient()
        client.force_authenticate(user=staff)
        client.raise_request_exception = False

        with patch(
            "instruments.views.InstrumentRequestEvent.objects.create",
            side_effect=Exception("Ошибка записи истории"),
        ):
            response = client.post(
                f"/api/instrument-requests/{request.id}/approve/"
            )

        self.assertEqual(response.status_code, 500)

        instrument.refresh_from_db()
        request.refresh_from_db()

        self.assertEqual(instrument.available_quantity, 5)
        self.assertEqual(request.status, "new")

        events_after = InstrumentRequestEvent.objects.filter(
            request=request
        ).count()

        self.assertEqual(events_after, events_before)

        print("\nПроверка отката транзакции")
        print(f"HTTP-статус ответа: {response.status_code}")
        print(f"Доступный остаток инструмента: {instrument.available_quantity}")
        print(f"Статус заявки: {request.status}")
        print(f"Событий до ошибки: {events_before}")
        print(f"Событий после ошибки: {events_after}")
        print("Все изменения успешно отменены.")