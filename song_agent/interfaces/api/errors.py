from http import HTTPStatus


DOMAIN_ERROR_STATUS = {
    "not_found": HTTPStatus.NOT_FOUND,
    "conflict": HTTPStatus.CONFLICT,
    "invalid": HTTPStatus.BAD_REQUEST,
    "unauthorized": HTTPStatus.UNAUTHORIZED,
}


def domain_error_status(kind: str) -> HTTPStatus:
    return DOMAIN_ERROR_STATUS.get(kind, HTTPStatus.INTERNAL_SERVER_ERROR)
