"""
Custom categories: list (defaults + custom), create, delete-with-reassign,
system protection, and integration with transaction/budget validation and the
advisor's category display resolution.
"""

from datetime import date

from models.user import db
from models.category import Category
from models.transaction import Transaction
from models.budget import Budget


class TestListAndCreate:
    def test_list_includes_defaults(self, client, auth_headers, user):
        res = client.get('/api/categories', headers=auth_headers)
        assert res.status_code == 200
        cats = res.get_json()
        values = {c['value'] for c in cats}
        assert 'FOOD_AND_DRINK' in values and 'UNCATEGORIZED' in values
        assert all(not c['is_custom'] for c in cats)  # only system so far

    def test_create_custom_category(self, client, auth_headers, user):
        res = client.post('/api/categories', headers=auth_headers,
                          json={'name': 'Dining Out', 'color': '#e27c4e', 'icon': 'utensils'})
        assert res.status_code == 201
        body = res.get_json()
        assert body['value'] == 'DINING_OUT'
        assert body['is_custom'] is True
        assert body['display_name'] == 'Dining Out'

        # Now appears in the list, flagged custom
        cats = client.get('/api/categories', headers=auth_headers).get_json()
        dining = next(c for c in cats if c['value'] == 'DINING_OUT')
        assert dining['is_custom'] is True

    def test_duplicate_name_rejected(self, client, auth_headers, user):
        client.post('/api/categories', headers=auth_headers,
                    json={'name': 'Groceries', 'color': '#a9bf49'})
        res = client.post('/api/categories', headers=auth_headers,
                          json={'name': 'groceries', 'color': '#6c9de6'})
        assert res.status_code == 400

    def test_name_colliding_with_default_rejected(self, client, auth_headers, user):
        res = client.post('/api/categories', headers=auth_headers,
                          json={'name': 'Food & Drink', 'color': '#6c9de6'})
        assert res.status_code == 400

    def test_bad_color_rejected(self, client, auth_headers, user):
        res = client.post('/api/categories', headers=auth_headers,
                          json={'name': 'Zzz', 'color': '#123456'})
        assert res.status_code == 400

    def test_value_uniqueness_suffix(self, client, auth_headers, user):
        # Two names that slugify to the same base get distinct values
        a = client.post('/api/categories', headers=auth_headers,
                        json={'name': 'Side Gig', 'color': '#a9bf49'}).get_json()
        b = client.post('/api/categories', headers=auth_headers,
                        json={'name': 'Side  Gig!', 'color': '#6c9de6'}).get_json()
        assert a['value'] == 'SIDE_GIG'
        assert b['value'] == 'SIDE_GIG_2'


class TestDeleteAndReassign:
    def _make_custom(self, client, auth_headers):
        return client.post('/api/categories', headers=auth_headers,
                           json={'name': 'Dining Out', 'color': '#e27c4e'}).get_json()

    def test_delete_reassigns_transactions_to_uncategorized(self, client, auth_headers, user):
        cat = self._make_custom(client, auth_headers)
        # a transaction in the custom category
        created = client.post('/api/transactions/', headers=auth_headers, json={
            'amount': 40, 'description': 'Kabob', 'category': 'DINING_OUT',
            'transaction_date': date.today().isoformat()}).get_json()
        assert created['category'] == 'DINING_OUT'

        res = client.delete(f"/api/categories/{cat['id']}", headers=auth_headers)
        assert res.status_code == 200
        assert res.get_json()['reassigned_transactions'] == 1

        fresh = Transaction.query.get(created['id'])
        assert fresh.category == 'UNCATEGORIZED'

    def test_delete_removes_budget_for_category(self, client, auth_headers, user):
        cat = self._make_custom(client, auth_headers)
        client.post('/api/budgets', headers=auth_headers,
                    json={'category': 'DINING_OUT', 'amount': 200})
        res = client.delete(f"/api/categories/{cat['id']}", headers=auth_headers)
        assert res.get_json()['removed_budgets'] == 1
        assert Budget.query.filter_by(user_id=user.id, category='DINING_OUT').count() == 0

    def test_cannot_delete_system_category(self, client, auth_headers, user):
        sys_cat = Category.query.filter_by(value='FOOD_AND_DRINK').one()
        res = client.delete(f'/api/categories/{sys_cat.id}', headers=auth_headers)
        assert res.status_code == 400
        assert Category.query.filter_by(value='FOOD_AND_DRINK').count() == 1

    def test_cannot_delete_other_users_category(self, client, auth_headers, user):
        from models.user import User
        other = User(email='o@x.com', first_name='O')
        other.set_password('password123')
        db.session.add(other)
        db.session.commit()
        theirs = Category(user_id=other.id, value='THEIRS', name='Theirs', color='#6c9de6', icon='tag')
        db.session.add(theirs)
        db.session.commit()
        res = client.delete(f'/api/categories/{theirs.id}', headers=auth_headers)
        assert res.status_code == 404


class TestIntegration:
    def test_transaction_accepts_custom_category(self, client, auth_headers, user):
        client.post('/api/categories', headers=auth_headers,
                    json={'name': 'Dining Out', 'color': '#e27c4e'})
        res = client.post('/api/transactions/', headers=auth_headers, json={
            'amount': 25, 'description': 'Tacos', 'category': 'DINING_OUT',
            'transaction_date': date.today().isoformat()})
        assert res.status_code == 201

    def test_transaction_rejects_unknown_category(self, client, auth_headers, user):
        res = client.post('/api/transactions/', headers=auth_headers, json={
            'amount': 25, 'description': 'x', 'category': 'NOT_A_REAL_CATEGORY',
            'transaction_date': date.today().isoformat()})
        assert res.status_code == 400

    def test_budget_accepts_custom_category(self, client, auth_headers, user):
        client.post('/api/categories', headers=auth_headers,
                    json={'name': 'Dining Out', 'color': '#e27c4e'})
        res = client.post('/api/budgets', headers=auth_headers,
                          json={'category': 'DINING_OUT', 'amount': 150})
        assert res.status_code == 201

    def test_advisor_context_resolves_custom_category_name(self, client, auth_headers, user):
        from utils.financial_context import format_context_for_llm, build_context_string
        client.post('/api/categories', headers=auth_headers,
                    json={'name': 'Dining Out', 'color': '#e27c4e'})
        client.post('/api/transactions/', headers=auth_headers, json={
            'amount': 60, 'description': 'Sushi', 'category': 'DINING_OUT',
            'transaction_date': date.today().isoformat()})

        text = build_context_string(format_context_for_llm(user.id))
        assert 'Dining Out' in text            # custom display name resolved
        assert 'DINING_OUT' not in text        # never the raw value
