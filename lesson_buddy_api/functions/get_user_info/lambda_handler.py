import json
import os

def handler(event, context):
    # The authorizer should have populated context with user claims
    # For example, event['requestContext']['authorizer']['claims']
    claims = event.get('requestContext', {}).get('authorizer', {}).get('claims', {})

    if not claims:
        return {
            'statusCode': 401,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*' # Adjust as needed
            },
            'body': json.dumps({'error': 'Not authorized or claims not found'})
        }

    user_info = {
        'sub': claims.get('sub'),
        'email': claims.get('email'),
        'username': claims.get('cognito:username') or claims.get('username'),
        # Add other claims you need
    }

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*' # Adjust as needed
        },
        'body': json.dumps(user_info)
    }
