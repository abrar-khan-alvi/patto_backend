from apps.profile_features.models import AccountDeletionRequest, DataExportRequest
from apps.profile_features.services import process_account_deletion_request, process_data_export_request


def process_data_export_request_task(export_request_id: str) -> str:
    export_request = DataExportRequest.objects.get(id=export_request_id)
    processed = process_data_export_request(export_request=export_request)
    return str(processed.id)


def process_account_deletion_request_task(deletion_request_id: str) -> str:
    deletion_request = AccountDeletionRequest.objects.get(id=deletion_request_id)
    processed = process_account_deletion_request(deletion_request=deletion_request)
    return str(processed.id)
