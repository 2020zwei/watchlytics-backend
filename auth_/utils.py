from rest_framework.views import exception_handler
from rest_framework.response import Response

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    
    if hasattr(exc, 'detail'):
        user_friendly_errors = {}
        
        for field, error_details in exc.detail.items():
            user_friendly_errors[field] = ' '.join([str(error) for error in error_details])
        
        return Response({
            'errors': user_friendly_errors,
            'status_code': response.status_code
        }, status=response.status_code)
    
    return response