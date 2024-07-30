from flask import Blueprint


healthcheck_blueprint = Blueprint("healthcheck", __name__, url_prefix="")


@healthcheck_blueprint.route("/_status")
def status():
    return "ok", 200
