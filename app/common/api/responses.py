from common.model.rest import ValidationErrorModel


responses={
            411: {'description': 'Invalid Header Error', 'model': ValidationErrorModel},
            412: {'description': 'JWT Decode Error', 'model': ValidationErrorModel},
            413: {'description': 'CSRF Error', 'model': ValidationErrorModel},
            414: {'description': 'Missing Token Error', 'model': ValidationErrorModel},
            415: {'description': 'Revoked Token Error', 'model': ValidationErrorModel},
            416: {'description': 'Access Token Required Error', 'model': ValidationErrorModel},
            417: {'description': 'Refresh Token Required Error', 'model': ValidationErrorModel},
            418: {'description': 'Fresh Token Required Error', 'model': ValidationErrorModel},
            422: {'description': 'Validation Error', 'model': ValidationErrorModel},
        }