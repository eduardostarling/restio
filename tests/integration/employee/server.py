import json
from pathlib import Path
from typing import Any, Dict, Set, Tuple

from flask import Flask, abort, jsonify, request

app = Flask(__name__)


# in-memory data

EMPLOYEES: Dict[int, Dict[str, Any]] = {}
# {
#     int: {
#         "key": int,
#         "name": str,
#         "age": int,
#         "address": str
#     }, ...
# }

COMPANIES: Dict[str, Dict[str, Any]] = {}
# {
#     str: {
#         "key": str,
#         "name": str
#     }
# }

COMPANY_EMPLOYEES: Set[Tuple[str, int]] = set()
# {
#     ("company_key", "employee_key"), ...
# }


def init_db():
    global EMPLOYEES, COMPANIES, COMPANY_EMPLOYEES

    CURRENT_DIRECTORY = Path(__file__).parent

    with open(CURRENT_DIRECTORY / "employees.json", "r") as fp:
        EMPLOYEES = {int(x["key"]): x for x in json.load(fp)}

    with open(CURRENT_DIRECTORY / "companies.json", "r") as fp:
        COMPANIES = {str(x["key"]): x for x in json.load(fp)}

    with open(CURRENT_DIRECTORY / "companies_employees.json", "r") as fp:
        COMPANY_EMPLOYEES = {(str(x[0]), int(x[1])) for x in json.load(fp)}


# GET


@app.route("/employees", methods=["GET"])
def employees():
    return jsonify(list(EMPLOYEES.values()))


@app.route("/employees/<int:key>", methods=["GET"])
def employee(key: int):
    if key not in EMPLOYEES:
        abort(404)
    return jsonify(EMPLOYEES[key])


@app.route("/companies", methods=["GET"])
def companies():
    return jsonify(list(COMPANIES.values()))


@app.route("/companies/<string:key>", methods=["GET"])
def company(key: str):
    if key not in COMPANIES:
        abort(404)
    return jsonify(COMPANIES[key])


@app.route("/companies/<string:key>/employees", methods=["GET"])
def company_employees(key: str):
    if key not in COMPANIES:
        abort(404)
    return jsonify(list(EMPLOYEES[ek] for ck, ek in COMPANY_EMPLOYEES if ck == key))


# POST


@app.route("/employees", methods=["POST"])
def employee_create():
    data = request.json

    # increments the biggest key in 1, and we have a new key
    new_key = max(int(k) for k in EMPLOYEES) + 1
    employee = EMPLOYEES.setdefault(new_key, {"key": new_key})

    employee["name"] = str(data["name"])
    employee["age"] = int(data["age"])
    employee["address"] = str(data["address"])

    return jsonify(), 201, {"location": f"/employees/{new_key}"}


# PUT


@app.route("/employees/<int:key>", methods=["PUT"])
def employee_update(key: int):
    if key not in EMPLOYEES:
        abort(404)

    data = request.json

    employee = EMPLOYEES[key]
    employee["name"] = str(data["name"])
    employee["age"] = int(data["age"])
    employee["address"] = str(data["address"])

    return "", 204


@app.route(
    "/companies/<string:company_key>/employees/<int:employee_key>", methods=["PUT"]
)
def company_employee_add(company_key: str, employee_key: int):
    if company_key not in COMPANIES or employee_key not in EMPLOYEES:
        abort(404)

    key = (company_key, employee_key)
    COMPANY_EMPLOYEES.add(key)

    return "", 204


# DELETE


@app.route("/employees/<int:key>", methods=["DELETE"])
def employee_delete(key: int):
    if key not in EMPLOYEES:
        abort(404)

    for _, ek in COMPANY_EMPLOYEES:
        if ek == key:
            abort(405)

    del EMPLOYEES[key]
    return "", 204


@app.route(
    "/companies/<string:company_key>/employees/<int:employee_key>", methods=["DELETE"]
)
def company_employee_delete(company_key: str, employee_key: int):
    if company_key not in COMPANIES or employee_key not in EMPLOYEES:
        abort(404)

    key = (company_key, employee_key)
    if key not in COMPANY_EMPLOYEES:
        abort(404)

    COMPANY_EMPLOYEES.remove(key)

    return "", 204
