from app.models.permission import Role
from app.models.user import User
from app.utils.security import create_access_token


async def _admin_headers(api):
    async with api.session_factory() as session:
        admin_role = Role(name="admin", description="Administrator")
        admin = User(
            username="admin-test",
            email="admin-test@example.com",
            hashed_password="unused",
            is_active=True,
            is_approved=True,
            role=admin_role,
        )
        session.add(admin)
        await session.commit()
        admin_id = admin.id
    return {"Authorization": f"Bearer {create_access_token(admin_id)}"}


async def test_admin_can_list_filter_and_approve_users(api):
    headers = await _admin_headers(api)

    listed = await api.client.get(
        "/api/v1/users",
        params={"page": 1, "size": 20},
        headers=headers,
    )
    assert listed.status_code == 200, listed.text
    users = {user["username"]: user for user in listed.json()["items"]}
    assert users["researcher"]["role_name"] == "researcher"
    assert users["viewer"]["role_name"] == "viewer"
    assert users["pending"]["role_name"] is None

    pending = await api.client.get(
        "/api/v1/users",
        params={"is_approved": False},
        headers=headers,
    )
    assert pending.status_code == 200
    assert pending.json()["total"] == 1
    assert pending.json()["items"][0]["username"] == "pending"

    roles = await api.client.get("/api/v1/users/roles/list", headers=headers)
    assert roles.status_code == 200
    viewer_role_id = next(
        role["id"] for role in roles.json() if role["name"] == "viewer"
    )

    approved = await api.client.patch(
        f"/api/v1/users/{api.user_ids['pending']}/approve",
        headers=headers,
        json={"role_id": viewer_role_id},
    )
    assert approved.status_code == 200

    refreshed = await api.client.get(
        "/api/v1/users",
        params={"search": "pending", "is_approved": True},
        headers=headers,
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["total"] == 1
    assert refreshed.json()["items"][0]["role_name"] == "viewer"
