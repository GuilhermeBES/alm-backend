def test_read_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to FastAPI with PostgreSQL"}


def test_create_item(client):
    response = client.post(
        "/items/", json={"title": "Test Item", "description": "Test Description"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Item"
    assert data["description"] == "Test Description"
    assert "id" in data


def test_read_items(client):
    client.post("/items/", json={"title": "Item 1"})
    client.post("/items/", json={"title": "Item 2"})

    response = client.get("/items/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_read_item(client):
    create_response = client.post("/items/", json={"title": "Test Item"})
    item_id = create_response.json()["id"]

    response = client.get(f"/items/{item_id}")
    assert response.status_code == 200
    assert response.json()["title"] == "Test Item"


def test_update_item(client):
    create_response = client.post("/items/", json={"title": "Original"})
    item_id = create_response.json()["id"]

    response = client.patch(f"/items/{item_id}", json={"title": "Updated"})
    assert response.status_code == 200
    assert response.json()["title"] == "Updated"


def test_delete_item(client):
    create_response = client.post("/items/", json={"title": "To Delete"})
    item_id = create_response.json()["id"]

    response = client.delete(f"/items/{item_id}")
    assert response.status_code == 200

    get_response = client.get(f"/items/{item_id}")
    assert get_response.status_code == 404
