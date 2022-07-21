from flask import Blueprint, abort, current_app, jsonify, make_response, request, send_file
from notifications_utils.base64_uuid import base64_to_bytes

from app import document_store
from app.utils.store import DocumentStoreError

download_blueprint = Blueprint('download', __name__, url_prefix='')


@download_blueprint.route('/services/<uuid:service_id>/documents/<uuid:document_id>', methods=['GET'])
def download_document(service_id, document_id):
    if 'key' not in request.args:
        return jsonify(error='Missing decryption key'), 400

    filename = request.args.get('filename')
    sending_method = request.args.get('sending_method', "link")

    try:
        key = base64_to_bytes(request.args['key'])
    except ValueError:
        return jsonify(error='Invalid decryption key'), 400

    try:
        document = document_store.get(service_id, document_id, key, sending_method)
    except DocumentStoreError as e:
        current_app.logger.info(
            'Failed to download document: {}'.format(e),
            extra={
                'service_id': service_id,
                'document_id': document_id,
            }
        )
        return jsonify(error=str(e)), 400

    response = make_response(send_file(
        document['body'],
        mimetype=document['mimetype'],
        # as_attachment can only be `True` if the filename is set
        as_attachment=(filename is not None),
        attachment_filename=filename,
    ))
    response.headers['Content-Length'] = document['size']
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'

    return response

# this endpoint mimics the url format of the current document-download-frontend links sent to the end user
@download_blueprint.route('/d/<base64_uuid:service_id>/<base64_uuid:document_id>', methods=['GET'])
def download_document_b64(service_id, document_id):
    if 'key' not in request.args:
        abort(404)

    filename = request.args.get('filename')
    sending_method = request.args.get('sending_method', 'link')

    try:
        key = base64_to_bytes(request.args['key'])
    except ValueError:
        abort(404)

    try:
        document = document_store.get(service_id, document_id, key, sending_method)
    except DocumentStoreError as e:
        current_app.logger.info(
            'Failed to download document: {}'.format(e),
            extra={
                'service_id': service_id,
                'document_id': document_id,
            }
        )
        abort(404)

    response = make_response(send_file(
        document['body'],
        mimetype=document['mimetype'],
        # as_attachment can only be `True` if the filename is set
        as_attachment=(filename is not None),
        attachment_filename=filename,
    ))
    response.headers['Content-Length'] = document['size']
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'

    return response
