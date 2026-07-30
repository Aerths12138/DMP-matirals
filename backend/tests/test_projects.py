async def test_project_owner_can_add_member_and_member_can_read(api):
    create_response = await api.client.post(
        "/api/v1/projects",
        headers=api.headers["researcher"],
        json={"name": "Battery project", "description": "Solid-state electrolyte"},
    )

    assert create_response.status_code == 201
    project = create_response.json()
    project_id = project["id"]
    assert project["owner_id"] == str(api.user_ids["researcher"])
    assert project["members"][0]["role"] == "owner"

    denied_response = await api.client.get(
        f"/api/v1/projects/{project_id}",
        headers=api.headers["viewer"],
    )
    assert denied_response.status_code == 403

    add_response = await api.client.post(
        f"/api/v1/projects/{project_id}/members",
        headers=api.headers["researcher"],
        json={"user_id": str(api.user_ids["viewer"]), "role": "viewer"},
    )
    assert add_response.status_code == 201

    get_response = await api.client.get(
        f"/api/v1/projects/{project_id}",
        headers=api.headers["viewer"],
    )
    assert get_response.status_code == 200
    assert len(get_response.json()["members"]) == 2

    update_response = await api.client.put(
        f"/api/v1/projects/{project_id}",
        headers=api.headers["viewer"],
        json={"name": "Unauthorized rename"},
    )
    assert update_response.status_code == 403


async def test_project_list_only_returns_memberships(api):
    create_response = await api.client.post(
        "/api/v1/projects",
        headers=api.headers["researcher"],
        json={"name": "Private project"},
    )
    assert create_response.status_code == 201

    owner_list = await api.client.get(
        "/api/v1/projects", headers=api.headers["researcher"]
    )


async def test_project_owner_can_update_and_remove_member(api):
    create_response = await api.client.post(
        "/api/v1/projects",
        headers=api.headers["researcher"],
        json={"name": "Membership project"},
    )
    project_id = create_response.json()["id"]
    viewer_id = str(api.user_ids["viewer"])

    add_response = await api.client.post(
        f"/api/v1/projects/{project_id}/members",
        headers=api.headers["researcher"],
        json={"user_id": viewer_id, "role": "viewer"},
    )
    assert add_response.status_code == 201

    update_response = await api.client.put(
        f"/api/v1/projects/{project_id}/members/{viewer_id}",
        headers=api.headers["researcher"],
        json={"role": "editor"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["role"] == "editor"

    remove_response = await api.client.delete(
        f"/api/v1/projects/{project_id}/members/{viewer_id}",
        headers=api.headers["researcher"],
    )
    assert remove_response.status_code == 204

    denied_response = await api.client.get(
        f"/api/v1/projects/{project_id}",
        headers=api.headers["viewer"],
    )
    assert denied_response.status_code == 403


async def test_user_directory_only_lists_approved_active_users(api):
    response = await api.client.get(
        "/api/v1/users/directory",
        headers=api.headers["researcher"],
    )

    assert response.status_code == 200
    usernames = {user["username"] for user in response.json()}
    assert usernames == {"outsider", "researcher", "viewer"}
