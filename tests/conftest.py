import pytest

def pytest_addoption(parser):
    parser.addoption("--geocodr-url", default="http://localhost:5000",
        help="URL of the external geocodr service to use for testing")
    parser.addoption("--solr-url", default="",
        help="URL of the Solr endpoint. pytest starts a local geocodr instance when using this option.")
    parser.addoption("--geocodr-mapping", default="",
        help="geocodr mapping config to use when using local geocodr instance (with --solr-url)")

@pytest.fixture(scope='session')
def geocodr_url(request):
    return request.config.getoption("--geocodr-url")

@pytest.fixture(scope='session')
def solr_url(request):
    return request.config.getoption("--solr-url")

@pytest.fixture(scope='session')
def geocodr_mapping(request):
    return request.config.getoption("--geocodr-mapping")
