from rest_framework.views import exception_handler
from rest_framework import response as res_, status
def custom_exception_handler(exc, context):
    # Call REST framework's default exception handler first,
    # to get the standard error response.
    if isinstance(exc, Exception):
        response = res_.Response(data={"message":f"Handling {str(exc)}",},status=status.HTTP_400_BAD_REQUEST)
    # response = exception_handler(exc, context)

    # Now add the HTTP status code to the response.
    if response is not None:
        response.data['status_code'] = response.status_code

    return response