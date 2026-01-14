#apps/contract_core/tests/test_services.py
from django.test import TestCase
from apps.identity.models import Company, User
from ..services import create_contract

class CreateContractTestCase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Тест-лицензиат", kind="licensee")
        self.user = User.objects.create_user(username="tester", password="123")

    def test_create(self):
        c = create_contract(
            number="2026-01-001",
            type="licensee_oneoff",
            company=self.company,
            customer_name="ООО Заказчик",
            total_sum=100_000,
            creator=self.user,
        )
        self.assertEqual(c.number, "2026-01-001")
        self.assertEqual(c.status, "draft")