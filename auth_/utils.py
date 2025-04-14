from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if isinstance(exc, (AuthenticationFailed, NotAuthenticated)):
        return Response({
            'message': 'Authentication credentials were not provided or invalid',
            'status_code': status.HTTP_401_UNAUTHORIZED
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    if response is not None and hasattr(exc, 'detail'):
        user_friendly_errors = {}
        
        if isinstance(exc.detail, dict):
            for field, error_details in exc.detail.items():
                if isinstance(error_details, list):
                    user_friendly_errors[field] = ' '.join([str(error) for error in error_details])
                else:
                    user_friendly_errors[field] = str(error_details)
        else:
            user_friendly_errors['error'] = str(exc.detail)
        
        return Response({
            'errors': user_friendly_errors,
            'status_code': response.status_code
        }, status=response.status_code)
    
    if response is None:
        return Response({
            'message': f'An unexpected error occurred: {str(exc)}',
            'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return response