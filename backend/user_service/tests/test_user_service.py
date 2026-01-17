# Run in root directory using: python -m pytest backend/user_service/tests/test_user_service.py -v
import asyncpg
import pytest
from backend.user_service.main import (
    app,
    create_access_token,
    get_user,
    hash_password,
    verify_password
)
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from jose import jwt
from pytest import mark, param
from unittest.mock import AsyncMock, MagicMock, patch

TEST_SECRET_KEY = "test-secret-32-chars-123456789"
ALGORITHM = "HS256"

@pytest.fixture
def mock_lifespan(monkeypatch):
    async def noop_lifespan(app):
        # Startup: nothing
        yield 
        # Shutdown: nothing
    
    monkeypatch.setattr('backend.user_service.main.lifespan', noop_lifespan)

    return app

@pytest.fixture
def client(mock_lifespan):
    """Use mocked lifespan client"""
    return TestClient(mock_lifespan)

@pytest.fixture(autouse=True)
def mock_all_secrets():
    with patch('backend.user_service.main.AUTH_SECRET_KEY', TEST_SECRET_KEY), \
         patch('backend.user_service.main.ALGORITHM', ALGORITHM):
        yield

@pytest.fixture
def mock_db_pool():
    mock_pool = MagicMock()
    
    cm = AsyncMock()
    mock_conn = AsyncMock()
    cm.__aenter__.return_value = mock_conn
    cm.__aexit__ = AsyncMock(return_value=None)
    
    mock_pool.acquire.return_value = cm
    
    with patch('backend.user_service.main.pool', mock_pool):
        yield mock_conn

class TestRegisterLogin:        
    @pytest.fixture
    def mock_db_functions(self):
        with patch('backend.user_service.main.get_user', new_callable=AsyncMock) as mock_get_user, \
            patch('backend.user_service.main.hash_password') as mock_hash, \
            patch('backend.user_service.main.verify_password') as mock_verify, \
            patch('backend.user_service.main.create_access_token') as mock_token:
            mock_hash.side_effect = lambda p: f"hashed_{p}"
            mock_verify.return_value = True
            mock_token.return_value = "mock_jwt_token"

            yield {'get_user': mock_get_user, 'hash_password': mock_hash, 
                'verify_password': mock_verify, 'create_access_token': mock_token}
        
    def test_register_success(self, mock_db_functions, mock_db_pool, client):
        mock_db_functions['get_user'].return_value = None
        mock_db_pool.fetchrow.return_value = {"id": 42}
        mock_db_pool.execute.return_value = "INSERT 0 1"
        
        response = client.post("/register", json={
            "username": "testuser", "email": "test@test.com", "password": "pass123"
        })
        
        data = response.json()
        assert response.status_code == 200
        assert data == {"user_id": 42}

    def test_register_user_exists(self, mock_db_functions, client):
        mock_get_user = mock_db_functions['get_user']
        mock_get_user.return_value = {"id": 1, "username": "testuser"}  # User exists, so cannot register
        
        response = client.post("/register", json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "testpass123"
        })
        
        assert response.status_code == 400
        assert response.json()["detail"] == "Username already registered"
        mock_get_user.assert_called_once_with("testuser")

    def test_register_db_insert_fail(self, mock_db_pool, client):
        mock_db_pool.acquire.return_value.__aenter__.return_value.execute.side_effect = asyncpg.UniqueViolationError
        response = client.post("/register", json={"username": "unique", "email": "test@test.com", "password": "passed"})
        
        assert response.status_code == 400

    @mark.parametrize("invalid_data, expected_field_error", [
        param(
            {"username": "ab", "email": "test@test.com", "password": "pass123"},
            "username\n  String should have at least 3 characters",
            id="username-too-short"
        ),
        param(
            {"username": "a" * 51, "email": "test@test.com", "password": "pass123"},
            "username\n  String should have at most 50 characters",
            id="username-too-long"
        ),
        param(
            {"username": "valid", "email": "not-an-email", "password": "pass123"},
            "email\n  value is not a valid email address",
            id="invalid-email"
        ),
        param(
            {"username": "valid", "email": "test@test.com", "password": "12345"},
            "password\n  String should have at least 6 characters",
            id="password-too-short"
        ),
    ])
    def test_register_validation(self, invalid_data, expected_field_error, client):
        response = client.post("/register", json=invalid_data)

        assert response.status_code == 422

    def test_login_success(self, mock_db_functions, client):
        mock_get_user = mock_db_functions['get_user']
        mock_get_user.return_value = {"id": 1, "username": "testuser", "hashed_password": "hashed_correctpass"}
        
        response = client.post("/login", json={
            "username": "testuser",
            "password": "correctpass"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "mock_jwt_token"
        assert data["token_type"] == "bearer"
        assert data["user_id"] == 1
        mock_get_user.assert_called_once_with("testuser")
        mock_db_functions['verify_password'].assert_called_once_with("correctpass", "hashed_correctpass")
        mock_db_functions['create_access_token'].assert_called_once()

    def test_login_no_user(self, mock_db_functions, client):
        mock_get_user = mock_db_functions['get_user']
        mock_get_user.return_value = None  # No user
        
        response = client.post("/login", json={
            "username": "testuser",
            "password": "wrongpass"
        })
        
        assert response.status_code == 401
        assert response.json()["detail"] == "Incorrect username or password"
        mock_get_user.assert_called_once_with("testuser")

    @mark.parametrize("invalid_data, expected_field_error", [
        param(
            {"username": "ab", "password": "pass123"},
            "username\n  String should have at least 3 characters",
            id="username-too-short"
        ),
        param(
            {"username": "a" * 51, "password": "pass123"},
            "username\n  String should have at most 50 characters",
            id="username-too-long"
        ),
        param(
            {"username": "valid", "password": "12345"},
            "password\n  String should have at least 6 characters",
            id="password-too-short"
        ),
    ])
    def test_login_validation(self, invalid_data, expected_field_error, client):
        response = client.post("/login", json=invalid_data)
        
        assert response.status_code == 422

class TestDBFunctions:
    @pytest.mark.asyncio
    async def test_get_user_found(self, mock_db_pool):
        mock_db_pool.fetchrow.return_value = {
            "id": 1, 
            "username": "found", 
            "email": "found@test.com", 
            "hashed_password": "hash"
        }
        
        user = await get_user("found")
        expected = {"id": 1, "username": "found", "email": "found@test.com", "hashed_password": "hash"}
        
        assert user == expected
        mock_db_pool.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, mock_db_pool):
        mock_db_pool.fetchrow.return_value = None
        user = await get_user("missing")

        assert user is None
        mock_db_pool.fetchrow.assert_called_once()

    def test_password_hashing(self):
        """Test password utils independently"""
        hashed = hash_password("password123")

        assert hashed.startswith("$2")  # bcrypt format
        assert verify_password("password123", hashed)
        assert not verify_password("xyz", hashed)

    def test_jwt_creation(self):
        data = {"username": "testuser", "user_id": 123}
        before_ts = int(datetime.now(timezone.utc).timestamp())
        token = create_access_token(data, expires_minutes=30)
        
        decoded = jwt.decode(token, TEST_SECRET_KEY, algorithms=[ALGORITHM])
        token_exp = decoded["exp"]
        
        expected_exp = before_ts + int(30 * 60)
        delta = abs(token_exp - expected_exp)
        
        assert delta < 5, f"Expected ~{expected_exp}, got {token_exp} (delta: {delta}s)"

    # def test_delete_user_success(self, mock_db_pool, client):
    #     """DELETE user exists → 200 {"deleted": "username"}"""
    #     mock_db_pool.execute.return_value = "DELETE 1"  # Success
        
    #     response = client.delete("/users/exists")
        
    #     assert response.status_code == 200
    #     assert response.json() == {"deleted": "exists"}
    #     mock_db_pool.execute.assert_called_once_with(
    #         "DELETE FROM users WHERE username = $1", "exists"
    #     )

    # def test_delete_user_not_found(self, mock_db_pool, client):
    #     """DELETE non-existent → 404 "User not found" """
    #     mock_db_pool.execute.return_value = "DELETE 0"  # No rows affected
        
    #     response = client.delete("/users/missing")
        
    #     assert response.status_code == 404
    #     assert response.json()["detail"] == "User not found"
    #     mock_db_pool.execute.assert_called_once_with(
    #         "DELETE FROM users WHERE username = $1", "missing"
    #     )

    # def test_delete_user_db_error(self, mock_db_pool, client):
    #     """DELETE raises DB exception → 500"""
    #     mock_db_pool.execute.side_effect = asyncpg.InternalError("DB panic")
        
    #     response = client.delete("/users/error")
        
    #     assert response.status_code == 500
    #     mock_db_pool.execute.assert_called_once_with(
    #         "DELETE FROM users WHERE username = $1", "error"
    #     )

    @mark.parametrize("username", [
        param("a", id="too-short"),
        param("a" * 51, id="too-long"),
    ])
    def test_delete_user_validation(self, username, client):
        response = client.delete(f"/users/{username}")
        
        assert response.status_code == 422
