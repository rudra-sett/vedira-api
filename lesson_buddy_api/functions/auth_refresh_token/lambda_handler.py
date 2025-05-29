import json
import boto3
import os

cognito_client = boto3.client('cognito-idp')

USER_POOL_ID = os.environ.get('USER_POOL_ID')
CLIENT_ID = os.environ.get('CLIENT_ID')

def handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        refresh_token = body.get('refreshToken')

        if not refresh_token:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Refresh token is required.'})
            }

        response = cognito_client.initiate_auth(
            ClientId=CLIENT_ID,
            AuthFlow='REFRESH_TOKEN_AUTH',
            AuthParameters={
                'REFRESH_TOKEN': refresh_token
            }
        )
        
        # Successful refresh token auth returns new tokens in AuthenticationResult
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'message': 'Token refresh successful.',
                'authenticationResult': response.get('AuthenticationResult')
            })
        }

    except cognito_client.exceptions.NotAuthorizedException:
        return {
            'statusCode': 401, # Unauthorized
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Invalid refresh token or session expired.'})
        }
    except cognito_client.exceptions.UserNotFoundException: # Should not happen with a valid refresh token flow
        return {
            'statusCode': 404, # Not Found
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'User not found.'})
        }
    except cognito_client.exceptions.UserNotConfirmedException: # Should not happen with a valid refresh token flow
        return {
            'statusCode': 403, # Forbidden
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'User is not confirmed.'})
        }
    except cognito_client.exceptions.TooManyRequestsException:
        return {
            'statusCode': 429,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Too many requests. Please try again later.'})
        }
    except Exception as e:
        print(f"Error during token refresh: {e}") # Log for debugging
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': f'An unexpected error occurred: {str(e)}'})
        }
