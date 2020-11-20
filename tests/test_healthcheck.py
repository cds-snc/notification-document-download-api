import pytest


@pytest.mark.parametrize(
    "endpoint",
    ['/', '/_status'],
)
def test_healthcheck_endpoint(client, endpoint):
    response = client.get(endpoint)
    assert response.status_code == 200
