from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class RegistrationTests(TestCase):
    def test_register_page_loads(self):
        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/register.html")
        self.assertContains(response, "Создание аккаунта")
        self.assertContains(response, reverse("login"))

    def test_successful_registration(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "newuser",
                "password1": "ComplexPass123!",
                "password2": "ComplexPass123!",
            },
            follow=True,
        )
        self.assertRedirects(response, "/")
        self.assertTrue(User.objects.filter(username="newuser").exists())
        self.assertTrue(response.context["user"].is_authenticated)

    def test_registration_password_mismatch(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "mismatchuser",
                "password1": "ComplexPass123!",
                "password2": "DifferentPass456!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="mismatchuser").exists())
        self.assertIn("password2", response.context["form"].errors)

    def test_authenticated_user_redirected_from_register(self):
        user = User.objects.create_user(username="testuser", password="PassWord123!")
        self.client.force_login(user)
        response = self.client.get(reverse("register"))
        self.assertRedirects(response, "/")

    def test_login_page_has_register_link(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/login.html")
        self.assertContains(response, reverse("register"))
