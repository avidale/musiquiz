import tgalice
import os
from pymongo import MongoClient
import mongomock
from dialog_manager import QuizDialogManager


if __name__ == '__main__':
    mongo_url = os.environ.get('MONGODB_URI')
    if mongo_url:
        mongo_client = MongoClient(mongo_url)
        mongo_db = mongo_client.get_default_database()
    else:
        mongo_client = mongomock.MongoClient()
        mongo_db = mongo_client.db
    mongo_logs = mongo_db.get_collection('message_logs')

    connector = tgalice.dialog_connector.DialogConnector(
        dialog_manager=QuizDialogManager.from_yaml('texts/quiz.yaml'),
        storage=tgalice.session_storage.MongoBasedStorage(database=mongo_db, collection_name='sessions')
    )
    server = tgalice.flask_server.FlaskServer(
        connector=connector, collection_for_logs=mongo_logs,
        not_log_id={'323149CB24DF1D7CE11CB9D3C80462CC84B478607FB65519C23A747A53D643AF'}
    )
    server.parse_args_and_run()
