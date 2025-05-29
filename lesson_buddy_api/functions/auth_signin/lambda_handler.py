import json
import boto3
import os

cognito_client = boto3.client('cognito-idp')

USER_POOL_ID = os.environ.get('USER_POOL_ID')
CLIENT_ID = os.environ.get('CLIENT_ID')

def handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        email = body.get('email') # Assuming email is used as the username
        password = body.get('password')

        if not all([email, password]):
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Email and password are required.'})
            }

        response = cognito_client.initiate_auth(
            ClientId=CLIENT_ID,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': email,
                'PASSWORD': password
            }
        )
        
        # If MFA is enabled and required, or other challenges, 'ChallengeName' will be in response.
        # For simplicity, this example assumes direct authentication or handles common challenges.
        if 'ChallengeName' in response:
            # Example: Handle NEW_PASSWORD_REQUIRED challenge
            if response['ChallengeName'] == 'NEW_PASSWORD_REQUIRED':
                return {
                    'statusCode': 200, # Or a specific code indicating challenge
                    'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                    'body': json.dumps({
                        'message': 'New password required.',
                        'challengeName': response['ChallengeName'],
                        'session': response['Session'],
                        'requiredAttributes': response.get('ChallengeParameters', {}).get('requiredAttributes')
                        # Client needs to call RespondToAuthChallenge with new password and session
                    })
                }
            # Add handling for other challenges like SMS_MFA, SOFTWARE_TOKEN_MFA etc.
            else:
                 return {
                    'statusCode': 401, # Unauthorized or specific challenge code
                    'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                    'body': json.dumps({
                        'error': f"Authentication challenge received: {response['ChallengeName']}",
                        'challengeName': response['ChallengeName'],
                        'session': response.get('Session'), # Include session if present
                        'challengeParameters': response.get('ChallengeParameters')
                    })
                }


        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'message': 'User sign in successful.',
                'authenticationResult': response.get('AuthenticationResult')
            })
        }

    except cognito_client.exceptions.NotAuthorizedException:
        return {
            'statusCode': 401, # Unauthorized
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Incorrect username or password.'})
        }
    except cognito_client.exceptions.UserNotFoundException:
        return {
            'statusCode': 404, # Not Found
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'User not found.'})
        }
    except cognito_client.exceptions.UserNotConfirmedException:
        return {
            'statusCode': 403, # Forbidden
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'User is not confirmed. Please confirm your account.'})
        }
    except cognito_client.exceptions.PasswordResetRequiredException:
        return {
            'statusCode': 400, # Bad Request or a custom code
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Password reset required for the user.'})
        }
    except cognito_client.exceptions.TooManyRequestsException:
        return {
            'statusCode': 429,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Too many requests. Please try again later.'})
        }
    except Exception as e:
        print(f"Error during sign_in: {e}") # Log for debugging
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': f'An unexpected error occurred: {str(e)}'})
        }
