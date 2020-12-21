import pytest
from flask.testing import FlaskClient

import tests.integration.employee.server as server
from restio.session import Session
from tests.integration.employee.client.api import ClientAPI
from tests.integration.employee.client.daos import CompanyDAO, EmployeeDAO


class CompanyEmployeeFixture:
    # tests setup

    @pytest.fixture(scope="function")
    def client(self) -> FlaskClient:
        server.app.config["TESTING"] = True

        with server.app.test_client() as client:
            with server.app.app_context():
                server.init_db()
            yield client  # type: ignore

    @pytest.fixture(scope="function")
    def api(self, client: FlaskClient) -> ClientAPI:
        return ClientAPI(client)

    @pytest.fixture(scope="function")
    def employee_dao(self, api) -> EmployeeDAO:
        return EmployeeDAO(api)

    @pytest.fixture(scope="function")
    def company_dao(self, api) -> CompanyDAO:
        return CompanyDAO(api)

    @pytest.fixture(scope="function")
    def session(
        self, api: ClientAPI, employee_dao: EmployeeDAO, company_dao: CompanyDAO
    ) -> Session:
        return self._get_session(api, employee_dao, company_dao)

    def _get_session(
        self, api: ClientAPI, employee_dao: EmployeeDAO, company_dao: CompanyDAO
    ):
        session = Session()
        session.register_dao(employee_dao)
        session.register_dao(company_dao)

        return session
