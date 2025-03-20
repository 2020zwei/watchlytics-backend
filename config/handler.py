from rest_framework.views import exception_handler

def custom_exception_handler(exc, context):
    print("called")
    if isinstance(exc, Exception):
        response = {"message":f"Handling {str(exc)}"}
    # response = exception_handler(exc, context)

    # Now add the HTTP status code to the response.
    if response is not None:
        response.data['status_code'] = response.status_code

    return response 