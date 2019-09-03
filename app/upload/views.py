import os
from flask import Blueprint, current_app, jsonify, request

from app import document_store
from app.utils import get_mime_type
from app.utils.mlwr import upload_to_mlwr
from app.utils.authentication import check_auth
from app.utils.urls import get_direct_file_url, get_frontend_download_url

upload_blueprint = Blueprint('upload', __name__, url_prefix='')
upload_blueprint.before_request(check_auth)


@upload_blueprint.route('/services/<uuid:service_id>/documents', methods=['POST'])
def upload_document(service_id):
    if 'document' not in request.files:
        return jsonify(error='No document upload'), 400

    mimetype = get_mime_type(request.files['document'])
    if mimetype not in current_app.config['ALLOWED_MIME_TYPES']:
        return jsonify(
            error="Unsupported document type '{}'. Supported types are: {}".format(
                mimetype,
                current_app.config['ALLOWED_MIME_TYPES']
            )
        ), 400
    file_content = request.files['document'].read()

    if os.getenv("MLWR_HOST"):
        sid = upload_to_mlwr(file_content)
    else:
        sid = False

    document = document_store.put(service_id, file_content, mimetype=mimetype)

    return jsonify(
        status='ok',
        document={
            'id': document['id'],
            'direct_file_url': get_direct_file_url(
                service_id=service_id,
                document_id=document['id'],
                key=document['encryption_key'],
            ),
            'url': get_frontend_download_url(
                service_id=service_id,
                document_id=document['id'],
                key=document['encryption_key'],
            ),
            'mlwr_sid': sid
        }
    ), 201
