from django.contrib.auth import authenticate, get_user_model
from django.db import IntegrityError
from django.test import TestCase

User = get_user_model()


class UserManagerTests(TestCase):
    def test_create_user_with_phone(self):
        user = User.objects.create_user(phone="+79990000001", password="StrongPass123!")
        self.assertEqual(user.phone, "+79990000001")
        self.assertIsNone(user.email)
        self.assertFalse(user.profile_completed)

    def test_create_user_without_phone_raises(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(phone="", password="StrongPass123!")

    def test_create_superuser(self):
        admin = User.objects.create_superuser(
            phone="+79990000002",
            email="admin@example.com",
            password="StrongPass123!",
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_phone_unique(self):
        User.objects.create_user(phone="+79990000010", password="StrongPass123!")
        with self.assertRaises(IntegrityError):
            User.objects.create_user(phone="+79990000010", password="StrongPass123!")


class AuthenticationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone="+79990000020", password="StrongPass123!")

    def test_authenticate_by_phone(self):
        u = authenticate(username="+79990000020", password="StrongPass123!")
        self.assertEqual(u, self.user)

    def test_authenticate_wrong_password(self):
        u = authenticate(username="+79990000020", password="wrong")
        self.assertIsNone(u)


class ProfileCompletionTests(TestCase):
    def test_profile_completed_flag_initially_false(self):
        user = User.objects.create_user(phone="+79990000030", password="StrongPass123!")
        self.assertFalse(user.profile_completed)

    def test_check_profile_completed_true_when_email_and_first_name_set(self):
        user = User.objects.create_user(phone="+79990000031", password="StrongPass123!")
        user.email = "test@example.com"
        user.first_name = "Иван"
        user.save()
        self.assertTrue(user.check_profile_completed())
        self.assertTrue(user.profile_completed)

    def test_check_profile_completed_false_when_email_missing(self):
        user = User.objects.create_user(phone="+79990000032", password="StrongPass123!")
        user.first_name = "Иван"
        user.save()
        self.assertFalse(user.check_profile_completed())
        self.assertFalse(user.profile_completed)

    def test_check_profile_completed_false_when_first_name_missing(self):
        user = User.objects.create_user(phone="+79990000033", password="StrongPass123!")
        user.email = "test@example.com"
        user.save()
        self.assertFalse(user.check_profile_completed())


class UserModelTests(TestCase):
    def test_get_full_name_with_first_name(self):
        user = User.objects.create_user(
            phone="+79990000040", password="StrongPass123!", first_name="Иван"
        )
        self.assertEqual(user.get_full_name(), "Иван")

    def test_get_full_name_with_both_names(self):
        user = User.objects.create_user(
            phone="+79990000041", password="StrongPass123!",
            first_name="Иван", last_name="Иванов",
        )
        self.assertEqual(user.get_full_name(), "Иван Иванов")

    def test_get_full_name_fallback_to_phone(self):
        user = User.objects.create_user(phone="+79990000042", password="StrongPass123!")
        self.assertEqual(user.get_full_name(), "+79990000042")

    def test_str_returns_phone_when_no_email(self):
        user = User.objects.create_user(phone="+79990000043", password="StrongPass123!")
        self.assertEqual(str(user), "+79990000043")

    def test_str_returns_email_when_set(self):
        user = User.objects.create_user(
            phone="+79990000044", password="StrongPass123!", email="test@example.com"
        )
        self.assertEqual(str(user), "test@example.com")
        