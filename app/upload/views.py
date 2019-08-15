from flask import Blueprint, current_app, jsonify, request

from app import document_store
from app.utils import get_mime_type
from app.utils.antivirus import AntivirusError
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

    try:
        # virus_free = antivirus_client.scan(request.files['document'])
        virus_free = True
    except AntivirusError:
        return jsonify(error='Antivirus API error'), 503

    if not virus_free:
        return jsonify(error="Document didn't pass the virus scan"), 400

    document = document_store.put(service_id, request.files['document'], mimetype=mimetype)

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
            )
        }
    ), 201
